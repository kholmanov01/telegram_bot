"""Tests for app.utils.dates — pure date/time helpers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
import pytz

from app.config.settings import settings
from app.utils import dates


def test_now_utc_is_timezone_aware() -> None:
    now = dates.now_utc()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_now_local_uses_app_timezone() -> None:
    now = dates.now_local()
    assert now.tzinfo is not None
    assert str(now.tzinfo) == str(pytz.timezone(settings.app_timezone))


def test_parse_date_ddmmyyyy() -> None:
    assert dates.parse_date("31.12.2025") == date(2025, 12, 31)


def test_parse_date_iso() -> None:
    assert dates.parse_date("2025-12-31") == date(2025, 12, 31)


def test_parse_date_invalid_raises() -> None:
    with pytest.raises(ValueError):
        dates.parse_date("not-a-date")


def test_parse_time_hhmm() -> None:
    assert dates.parse_time("18:30") == time(18, 30)


def test_parse_time_invalid_raises() -> None:
    with pytest.raises(ValueError):
        dates.parse_time("25:99")


def test_build_deadline_returns_utc() -> None:
    dl = dates.build_deadline(date(2025, 6, 15), time(9, 0), "Asia/Tashkent")
    assert dl.tzinfo is not None
    # Tashkent is UTC+5 → 09:00 local == 04:00 UTC
    assert dl.utcoffset() == timedelta(0)
    assert dl.hour == 4


def test_format_datetime_none() -> None:
    assert dates.format_datetime(None) == ""


def test_format_datetime_format() -> None:
    # format_datetime renders in the configured app timezone (Asia/Tashkent, UTC+5).
    dt = datetime(2025, 6, 15, 9, 30, tzinfo=timezone.utc)  # 09:30 UTC
    formatted = dates.format_datetime(dt)
    assert "15.06.2025" in formatted
    # 09:30 UTC == 14:30 in Asia/Tashkent (UTC+5)
    assert "14:30" in formatted
    assert len(formatted) == 16  # DD.MM.YYYY HH:MM


def test_remaining_time_past() -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    assert dates.remaining_time(past) == "O'tib ketgan"


def test_remaining_time_future_has_units() -> None:
    # Use a large enough window so sub-second test timing drift cannot
    # flip the day/hour boundaries.
    future = datetime.now(timezone.utc) + timedelta(days=2, hours=5)
    result = dates.remaining_time(future)
    assert "2k" in result  # 2 kun (days)
    assert "O'tib" not in result


def test_remaining_time_none() -> None:
    assert dates.remaining_time(None) == ""  # type: ignore[arg-type]


def test_start_of_today_local_aware() -> None:
    start = dates.start_of_today_local()
    assert start.tzinfo is not None
    assert start.hour == 0 and start.minute == 0
