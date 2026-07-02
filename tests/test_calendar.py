"""Tests for the inline calendar and time-picker keyboards."""

from __future__ import annotations

from datetime import date

import pytest

from app.bot.keyboards.calendar import (
    CalendarCallback,
    TimePickerCallback,
    calendar_keyboard,
    hour_keyboard,
    minute_keyboard,
    shift_month,
)


def test_calendar_callback_roundtrip() -> None:
    cb = CalendarCallback(action="day", year="2025", month="7", day="15")
    parsed = CalendarCallback.unpack(cb.pack())
    assert parsed.action == "day"
    assert parsed.year == "2025"
    assert parsed.month == "7"
    assert parsed.day == "15"


def test_calendar_callback_nav_roundtrip() -> None:
    cb = CalendarCallback(action="nav", year="2025", month="7", direction="-1")
    parsed = CalendarCallback.unpack(cb.pack())
    assert parsed.action == "nav"
    assert parsed.direction == "-1"


def test_time_picker_callback_hour_roundtrip() -> None:
    cb = TimePickerCallback(action="hour", value="14")
    parsed = TimePickerCallback.unpack(cb.pack())
    assert parsed.action == "hour"
    assert parsed.value == "14"


def test_time_picker_callback_minute_roundtrip() -> None:
    cb = TimePickerCallback(action="minute", hour="14", value="30")
    parsed = TimePickerCallback.unpack(cb.pack())
    assert parsed.action == "minute"
    assert parsed.hour == "14"
    assert parsed.value == "30"


def test_calendar_has_header_weekdays_and_footer() -> None:
    kb = calendar_keyboard(2025, 7)
    rows = kb.inline_keyboard
    # Header row: ‹ | Month YYYY | ›
    assert len(rows[0]) == 3
    assert rows[0][0].text == "‹"
    assert rows[0][2].text == "›"
    assert "Iyul" in rows[0][1].text
    assert "2025" in rows[0][1].text
    # Weekday header: 7 Uzbek abbreviations, Monday-first.
    assert [b.text for b in rows[1]] == ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    # Footer: today + cancel.
    assert any("Bugun" in b.text for b in rows[-1])
    assert any("Bekor" in b.text for b in rows[-1])


def test_calendar_day_buttons_are_clickable() -> None:
    """A future month must have clickable day buttons (action='day')."""
    from app.utils.dates import now_local
    today = now_local().date()
    # Use next month so all days are in the future.
    ny, nm = shift_month(today.year, today.month, 1)
    kb = calendar_keyboard(ny, nm)
    day_callbacks = []
    for row in kb.inline_keyboard[2:-1]:  # skip header, weekdays, footer
        for btn in row:
            if btn.callback_data:
                try:
                    cb = CalendarCallback.unpack(btn.callback_data)
                    if cb.action == "day":
                        day_callbacks.append(cb)
                except Exception:
                    pass
    assert len(day_callbacks) > 0
    # All day callbacks should be in the chosen future month.
    for cb in day_callbacks:
        assert cb.year == str(ny) and cb.month == str(nm)


def test_hour_keyboard_has_24_hours_plus_cancel() -> None:
    kb = hour_keyboard()
    rows = kb.inline_keyboard
    hour_count = 0
    cancel_found = False
    for row in rows:
        for btn in row:
            if btn.callback_data:
                try:
                    cb = TimePickerCallback.unpack(btn.callback_data)
                    if cb.action == "hour":
                        hour_count += 1
                    elif cb.action == "cancel":
                        cancel_found = True
                except Exception:
                    pass
    assert hour_count == 24
    assert cancel_found


def test_minute_keyboard_has_12_minutes_plus_nav() -> None:
    kb = minute_keyboard(14)
    rows = kb.inline_keyboard
    minute_count = 0
    back_found = False
    for row in rows:
        for btn in row:
            if btn.callback_data:
                try:
                    cb = TimePickerCallback.unpack(btn.callback_data)
                    if cb.action == "minute":
                        minute_count += 1
                    elif cb.action == "back":
                        back_found = True
                except Exception:
                    pass
    assert minute_count == 12
    assert back_found


@pytest.mark.parametrize(
    "year,month,direction,expected",
    [
        (2025, 7, 1, (2025, 8)),
        (2025, 7, -1, (2025, 6)),
        (2025, 12, 1, (2026, 1)),
        (2025, 1, -1, (2024, 12)),
        (2025, 6, 1, (2025, 7)),
    ],
)
def test_shift_month(year: int, month: int, direction: int, expected: tuple[int, int]) -> None:
    assert shift_month(year, month, direction) == expected
