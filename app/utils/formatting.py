"""HTML message & card formatting helpers for Telegram.

All output is HTML (the bot uses HTML parse mode). User-provided text MUST be
escaped via :func:`escape_html` to prevent HTML injection and broken layout.
"""

from __future__ import annotations

from html import escape
from typing import Any

from app.models.enums import TaskPriority, TaskStatus

from app.utils import dates


# A stable divider line used between card sections.
_DIVIDER = "━━━━━━━━━━━━━━"


def escape_html(text: str | None) -> str:
    """Escape ``&``, ``<`` and ``>`` for safe inclusion in HTML.

    ``None`` becomes an empty string.

    :param text: Raw text (may be ``None``).
    :returns: HTML-safe string.
    """
    if text is None:
        return ""
    return escape(str(text), quote=False)


def divider() -> str:
    """Return the standard divider line used in cards."""
    return _DIVIDER


def _normalize_priority(priority: Any) -> TaskPriority:
    """Coerce a raw priority value into a :class:`TaskPriority` enum."""
    if isinstance(priority, TaskPriority):
        return priority
    if isinstance(priority, str):
        try:
            return TaskPriority(priority)
        except ValueError:
            pass
    return TaskPriority.MEDIUM


def _normalize_status(status: Any) -> TaskStatus:
    """Coerce a raw status value into a :class:`TaskStatus` enum."""
    if isinstance(status, TaskStatus):
        return status
    if isinstance(status, str):
        try:
            return TaskStatus(status)
        except ValueError:
            pass
    return TaskStatus.PENDING


def task_card(
    task: Any,
    employee: Any | None = None,
    with_remaining: bool = True,
    header: str | None = None,
) -> str:
    """Render a beautiful HTML task card.

    The ``task`` object is duck-typed. It should expose:

    - ``title`` (str)
    - ``description`` (str | None)
    - ``priority`` (``TaskPriority`` or its string value)
    - ``deadline`` (timezone-aware datetime)
    - optionally ``status`` (``TaskStatus`` or its string value)
    - optionally ``id`` (int)

    :param task: Task-like object.
    :param employee: Optional employee object (uses ``full_name`` if present).
    :param with_remaining: If True, render the "Qolgan vaqt" line.
    :param header: Optional custom header (e.g. "📌 Yangi vazifa"). When
        ``None``, defaults to "📌 Vazifa".
    :returns: HTML string.
    """
    title = escape_html(getattr(task, "title", None))
    description = escape_html(getattr(task, "description", None)) or "—"
    priority = _normalize_priority(getattr(task, "priority", None))
    deadline = getattr(task, "deadline", None)
    deadline_str = dates.format_datetime(deadline)

    lines: list[str] = [
        divider(),
        header if header is not None else "📌 Vazifa",
    ]

    task_id = getattr(task, "id", None)
    if task_id is not None:
        lines.append(f"<b>ID:</b> #{escape_html(str(task_id))}")

    lines.append(f"<b>Sarlavha:</b> {title}")
    lines.append(f"<b>Ta'rifi:</b> {description}")
    lines.append(f"<b>Ustuvorlik:</b> {priority.emoji} {priority.label}")

    if employee is not None:
        emp_name = escape_html(getattr(employee, "full_name", None)) or "—"
        emp_code = escape_html(getattr(employee, "code", None))
        emp_part = emp_name
        if emp_code:
            emp_part = f"{emp_code} · {emp_name}"
        lines.append(f"<b>Xodim:</b> {emp_part}")

    if deadline_str:
        lines.append(f"<b>Muddat:</b> {deadline_str}")

    if with_remaining and deadline is not None:
        lines.append(f"<b>Qolgan vaqt:</b> {dates.remaining_time(deadline)}")

    lines.append(divider())
    return "\n".join(lines)


def employee_card(employee: Any) -> str:
    """Render an employee profile card.

    Fields used (all optional except ``full_name``):

    - ``code`` (e.g. EMP001)
    - ``full_name``
    - ``position``
    - ``department``
    - ``is_active``

    :param employee: Employee-like object.
    :returns: HTML string.
    """
    code = escape_html(getattr(employee, "code", None)) or "—"
    full_name = escape_html(getattr(employee, "full_name", None)) or "—"
    position = escape_html(getattr(employee, "position", None)) or "—"
    department = escape_html(getattr(employee, "department", None)) or "—"
    is_active = bool(getattr(employee, "is_active", True))
    state = "Faol" if is_active else "Nofaol"
    state_emoji = "🟢" if is_active else "🔴"

    return "\n".join(
        [
            divider(),
            f"📛 <b>{code}</b>",
            f"<b>Ism:</b> {full_name}",
            f"<b>Lavozim:</b> {position}",
            f"<b>Bo'lim:</b> {department}",
            f"<b>Holat:</b> {state_emoji} {state}",
            divider(),
        ]
    )


def stats_card(stats: dict) -> str:
    """Render a statistics dict as a compact HTML card.

    Recognised keys (all optional): ``total``, ``pending``, ``completed``,
    ``expired``, ``archived``, ``success_rate`` (0-100 float), ``avg_completion_time``
    (human-readable string), ``completed_today``, ``expired_today``.

    Any other keys are rendered as ``emoji key: value`` lines with a generic
    "📊" prefix.

    :param stats: Mapping of statistic name to value.
    :returns: HTML string.
    """
    lines: list[str] = [divider(), "📊 <b>Statistika</b>"]

    known: list[tuple[str, str, str]] = [
        ("total", "🔢", "Jami vazifalar"),
        ("pending", "⏳", "Kutilmoqda"),
        ("completed", "✅", "Bajarilgan"),
        ("expired", "❌", "Muddati o'tgan"),
        ("archived", "🗄", "Arxivlangan"),
        ("completed_today", "📅", "Bugun bajarilgan"),
        ("expired_today", "📅", "Bugun muddati o'tgan"),
        ("success_rate", "🎯", "Muvaffaqiyat darajasi"),
        ("avg_completion_time", "⏱", "O'rtacha bajarish vaqti"),
    ]

    used_keys: set[str] = set()
    for key, emoji, label in known:
        if key in stats and stats[key] is not None:
            value = stats[key]
            if key == "success_rate":
                try:
                    value = f"{float(value):.1f}%"
                except (TypeError, ValueError):
                    value = escape_html(str(value))
            else:
                value = escape_html(str(value))
            lines.append(f"{emoji} <b>{label}:</b> {value}")
            used_keys.add(key)

    # Render any extra keys generically.
    for key, value in stats.items():
        if key in used_keys or value is None:
            continue
        label = escape_html(str(key).replace("_", " ").title())
        lines.append(f"📊 <b>{label}:</b> {escape_html(str(value))}")

    lines.append(divider())
    return "\n".join(lines)


def progress_bar(percent: float, width: int = 10) -> str:
    """Render a textual progress bar using ``█`` and ``░`` characters.

    :param percent: A value between 0 and 100. Values outside the range are
        clamped.
    :param width: Number of characters in the bar.
    :returns: A string like ``"██████░░░░"`` (6 of 10 filled).
    """
    if width <= 0:
        return ""
    pct = max(0.0, min(100.0, float(percent)))
    filled = round(pct / 100.0 * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def centered(text: str) -> str:
    """Wrap a line with separator characters for a clean, centered look.

    Telegram has no real text centering, so we frame the content with the
    standard divider on both sides.

    :param text: Content line.
    :returns: Framed string.
    """
    if not text:
        return divider()
    return f"{divider()}\n{text}\n{divider()}"
