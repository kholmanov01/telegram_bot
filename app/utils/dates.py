"""Time and date helpers.

All timezone handling goes through :mod:`pytz` and uses the application's
configured timezone (``settings.app_timezone``). Database storage is always
timezone-aware UTC; display is always in the local application timezone.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytz

from app.config.settings import settings


def _get_tz(tz_name: str | None = None) -> pytz.BaseTzInfo:
    """Return a pytz timezone, defaulting to the application timezone.

    :param tz_name: Optional IANA timezone name. If ``None`` or empty,
        ``settings.app_timezone`` is used.
    :returns: A :class:`pytz.BaseTzInfo` instance.
    """
    return pytz.timezone(tz_name or settings.app_timezone)


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    """Return the current time in the application timezone."""
    return now_utc().astimezone(_get_tz())


def to_local(dt: datetime | None) -> datetime | None:
    """Convert a (possibly tz-aware UTC) datetime to the application timezone.

    Naive datetimes are assumed to already be in UTC. ``None`` is passed
    through unchanged.

    :param dt: Datetime to convert (or ``None``).
    :returns: Datetime in the app timezone, or ``None``.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume UTC for naive datetimes coming from the DB.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_get_tz())


def parse_date(date_str: str) -> date:
    """Parse a date string.

    Accepts both ``DD.MM.YYYY`` and ``YYYY-MM-DD``. Raises :class:`ValueError`
    on invalid input (including impossible calendar dates).

    :param date_str: Date string to parse.
    :returns: A :class:`datetime.date` instance.
    :raises ValueError: If the string cannot be parsed.
    """
    if not isinstance(date_str, str):
        raise ValueError("Date must be a string")
    s = date_str.strip()
    if not s:
        raise ValueError("Date string is empty")
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Invalid date format: {date_str!r}. Expected DD.MM.YYYY or YYYY-MM-DD"
    )


def parse_time(time_str: str) -> time:
    """Parse a 24-hour ``HH:MM`` time string.

    :param time_str: Time string to parse.
    :returns: A :class:`datetime.time` instance.
    :raises ValueError: If the string cannot be parsed.
    """
    if not isinstance(time_str, str):
        raise ValueError("Time must be a string")
    s = time_str.strip()
    if not s:
        raise ValueError("Time string is empty")
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time format: {time_str!r}. Expected HH:MM")


def build_deadline(d: date, t: time, tz_name: str | None = None) -> datetime:
    """Combine a date and a time in a given timezone and return tz-aware UTC.

    This is used to convert user-entered local deadline components into the
    timezone-aware UTC datetime stored in the database.

    :param d: Local date.
    :param t: Local time.
    :param tz_name: IANA timezone name (default: ``settings.app_timezone``).
    :returns: Timezone-aware UTC datetime.
    """
    tz = _get_tz(tz_name)
    # pytz.localize is the correct way to attach a pytz tz to a naive datetime.
    local_dt = tz.localize(datetime.combine(d, t))
    return local_dt.astimezone(timezone.utc)


def format_datetime(dt: datetime | None, tz_name: str | None = None) -> str:
    """Format a datetime as ``DD.MM.YYYY HH:MM`` in the local timezone.

    Returns an empty string when ``dt`` is ``None``.

    :param dt: Datetime to format (may be ``None``).
    :param tz_name: Optional timezone override.
    :returns: Formatted string or "".
    """
    if dt is None:
        return ""
    local_dt = to_local(dt)
    if local_dt is None:
        return ""
    return local_dt.strftime("%d.%m.%Y %H:%M")


def format_date(d: date | datetime | None) -> str:
    """Format a date or datetime as ``DD.MM.YYYY``.

    Returns an empty string when ``d`` is ``None``. Datetime instances are
    first converted to the local timezone.

    :param d: Date or datetime to format (may be ``None``).
    :returns: Formatted string or "".
    """
    if d is None:
        return ""
    if isinstance(d, datetime):
        local_dt = to_local(d)
        if local_dt is None:
            return ""
        return local_dt.strftime("%d.%m.%Y")
    return d.strftime("%d.%m.%Y")


def remaining_time(deadline: datetime) -> str:
    """Return a compact, human-readable remaining-time string.

    Examples (Uzbek-ish):

    - Future: ``"2s 13o 45daqiqa"`` (soat / daqiqa).
    - Less than an hour: ``"12daqiqa"``.
    - Less than a minute: ``"45soniya"``.
    - Past: ``"O'tib ketgan"``.

    The returned string is intentionally compact so it fits on one card line.

    :param deadline: Timezone-aware deadline datetime (UTC or any tz).
    :returns: Compact remaining-time string.
    """
    if deadline is None:
        return ""
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    now = now_utc()
    delta = deadline - now

    if delta.total_seconds() <= 0:
        return "O'tib ketgan"

    total_seconds = int(delta.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}k")  # kun
    if hours > 0:
        parts.append(f"{hours}s")  # soat
    if minutes > 0:
        parts.append(f"{minutes}daqiqa")
    if not parts:
        # Less than a minute remaining.
        parts.append(f"{max(seconds, 0)}soniya")
    return " ".join(parts)


def start_of_today_local() -> datetime:
    """Return midnight (00:00:00) today in the application timezone."""
    tz = _get_tz()
    local_now = now_local()
    return tz.localize(datetime.combine(local_now.date(), time.min))


def end_of_today_local() -> datetime:
    """Return 23:59:59 today in the application timezone."""
    tz = _get_tz()
    local_now = now_local()
    return tz.localize(
        datetime.combine(local_now.date(), time.max)
    )


def start_of_week_local() -> datetime:
    """Return midnight (00:00:00) of the current week's Monday in app tz."""
    tz = _get_tz()
    local_now = now_local()
    # Monday is 0, Sunday is 6.
    monday = local_now.date() - timedelta(days=local_now.weekday())
    return tz.localize(datetime.combine(monday, time.min))


def start_of_month_local() -> datetime:
    """Return midnight (00:00:00) of the first day of the current month."""
    tz = _get_tz()
    local_now = now_local()
    first = local_now.date().replace(day=1)
    return tz.localize(datetime.combine(first, time.min))
