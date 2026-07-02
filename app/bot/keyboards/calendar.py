"""Inline calendar and time-picker keyboards for deadline selection.

These keyboards replace plain-text date / time entry in the task-creation
wizard with a tappable, real-time calendar (month view, Monday-first) and
a two-step time picker (hour grid → minute grid).

All buttons use :class:`CallbackData` factories — no text parsing.
"""

from __future__ import annotations

import calendar as _calendar
from typing import Any

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.dates import now_local


# Uzbek month names (nominative case).
_MONTHS_UZ: tuple[str, ...] = (
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
)

# Uzbek weekday abbreviations, Monday-first.
_WEEKDAYS_UZ: tuple[str, ...] = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")


# --------------------------------------------------------------------------- #
# Callback data factories
# --------------------------------------------------------------------------- #
class CalendarCallback(CallbackData, prefix="cal"):
    """Calendar inline button.

    Args:
        action: ``day`` (pick a day), ``nav`` (prev/next month),
            ``today`` (jump to & pick today), ``cancel`` (abort wizard),
            ``ignore`` (no-op button — headers / blanks / past days).
        year: Year as string (e.g. ``"2025"``).
        month: Month 1-12 as string.
        day: Day 1-31 as string (``"0"`` when N/A).
        direction: ``"-1"`` for previous month, ``"1"`` for next (only for ``nav``).
    """

    action: str
    year: str
    month: str
    day: str = "0"
    direction: str = "0"


class TimePickerCallback(CallbackData, prefix="tp"):
    """Time-picker inline button.

    Args:
        action: ``hour`` (pick an hour → show minute grid), ``minute``
            (final pick → advance), ``back`` (return to hour grid),
            ``cancel`` (abort).
        hour: Selected hour carried through the minute step (``"0"``-``"23"``).
        value: The value being picked (hour or minute).
    """

    action: str
    hour: str = "0"
    value: str = "0"


# --------------------------------------------------------------------------- #
# Calendar
# --------------------------------------------------------------------------- #
def calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Build a month-view calendar inline keyboard.

    Past days are rendered as dimmed, non-clickable buttons. Today is
    highlighted with surrounding dots (``•15•``).

    Args:
        year: Year to display.
        month: Month to display (1-12).

    Returns:
        An :class:`InlineKeyboardMarkup` with the month grid.
    """
    today = now_local().date()
    rows: list[list[InlineKeyboardButton]] = []

    # --- Header: ‹  Month YYYY  › ---
    rows.append([
        InlineKeyboardButton(
            text="‹",
            callback_data=CalendarCallback(
                action="nav", year=str(year), month=str(month), direction="-1"
            ).pack(),
        ),
        InlineKeyboardButton(
            text=f"📅  {_MONTHS_UZ[month - 1]} {year}",
            callback_data=CalendarCallback(
                action="ignore", year=str(year), month=str(month)
            ).pack(),
        ),
        InlineKeyboardButton(
            text="›",
            callback_data=CalendarCallback(
                action="nav", year=str(year), month=str(month), direction="1"
            ).pack(),
        ),
    ])

    # --- Weekday header row (Monday-first) ---
    rows.append([
        InlineKeyboardButton(
            text=d,
            callback_data=CalendarCallback(
                action="ignore", year=str(year), month=str(month)
            ).pack(),
        )
        for d in _WEEKDAYS_UZ
    ])

    # --- Day grid ---
    cal = _calendar.Calendar(firstweekday=0)  # 0 = Monday
    for week in cal.monthdatescalendar(year, month):
        row: list[InlineKeyboardButton] = []
        for d in week:
            if d.month != month:
                # Day belongs to adjacent month — render as blank.
                row.append(InlineKeyboardButton(
                    text=" ",
                    callback_data=CalendarCallback(
                        action="ignore", year=str(year), month=str(month)
                    ).pack(),
                ))
            else:
                is_today = d == today
                is_past = d < today
                if is_past:
                    # Dimmed, non-clickable.
                    row.append(InlineKeyboardButton(
                        text=f" {d.day} ",
                        callback_data=CalendarCallback(
                            action="ignore", year=str(year), month=str(month)
                        ).pack(),
                    ))
                elif is_today:
                    row.append(InlineKeyboardButton(
                        text=f"•{d.day}•",
                        callback_data=CalendarCallback(
                            action="day", year=str(year), month=str(month), day=str(d.day)
                        ).pack(),
                    ))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(d.day),
                        callback_data=CalendarCallback(
                            action="day", year=str(year), month=str(month), day=str(d.day)
                        ).pack(),
                    ))
        rows.append(row)

    # --- Footer: today + cancel ---
    rows.append([
        InlineKeyboardButton(
            text="📅 Bugun",
            callback_data=CalendarCallback(
                action="today", year=str(year), month=str(month)
            ).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data=CalendarCallback(
                action="cancel", year=str(year), month=str(month)
            ).pack(),
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# --------------------------------------------------------------------------- #
# Time picker
# --------------------------------------------------------------------------- #
# Minutes offered in the minute grid (every 5 minutes).
_MINUTES: tuple[int, ...] = (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55)


def hour_keyboard() -> InlineKeyboardMarkup:
    """Build the hour-selection grid (00-23, six per row → four rows).

    Returns:
        An :class:`InlineKeyboardMarkup` with 24 hour buttons + cancel.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for start in range(0, 24, 6):
        rows.append([
            InlineKeyboardButton(
                text=f"{h:02d}:00",
                callback_data=TimePickerCallback(action="hour", value=str(h)).pack(),
            )
            for h in range(start, start + 6)
        ])
    rows.append([
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data=TimePickerCallback(action="cancel").pack(),
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def minute_keyboard(hour: int) -> InlineKeyboardMarkup:
    """Build the minute-selection grid for a chosen hour.

    Args:
        hour: The hour (0-23) chosen in the previous step.

    Returns:
        An :class:`InlineKeyboardMarkup` with a header showing the chosen
        hour, 12 minute buttons (every 5 min), and back/cancel buttons.
    """
    rows: list[list[InlineKeyboardButton]] = []
    # Header showing the selected hour.
    rows.append([
        InlineKeyboardButton(
            text=f"⏰  {hour:02d}:__  (daqiqani tanlang)",
            callback_data=TimePickerCallback(action="back", hour=str(hour)).pack(),
        ),
    ])
    # Minute buttons — 4 per row → 3 rows.
    for start in range(0, 12, 4):
        rows.append([
            InlineKeyboardButton(
                text=f"{hour:02d}:{m:02d}",
                callback_data=TimePickerCallback(
                    action="minute", hour=str(hour), value=str(m)
                ).pack(),
            )
            for m in _MINUTES[start:start + 4]
        ])
    # Footer: back + cancel.
    rows.append([
        InlineKeyboardButton(
            text="‹ Soatga qaytish",
            callback_data=TimePickerCallback(action="back", hour=str(hour)).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data=TimePickerCallback(action="cancel").pack(),
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def shift_month(year: int, month: int, direction: int) -> tuple[int, int]:
    """Return the (year, month) shifted by ``direction`` months.

    Args:
        year: Current year.
        month: Current month (1-12).
        direction: ``-1`` for previous month, ``+1`` for next month.

    Returns:
        A ``(year, month)`` tuple after the shift.
    """
    idx = (month - 1) + direction
    if idx < 0:
        year -= 1
        idx = 11
    elif idx > 11:
        year += 1
        idx = 0
    return year, idx + 1


__all__ = [
    "CalendarCallback",
    "TimePickerCallback",
    "calendar_keyboard",
    "hour_keyboard",
    "minute_keyboard",
    "shift_month",
]
