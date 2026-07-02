"""Keyboard builders package.

Re-exports the public keyboard builders and callback factories so handlers can
import everything from a single location::

    from app.bot.keyboards import admin_menu, task_card_inline, TaskCallback
"""

from __future__ import annotations

from app.bot.keyboards.callbacks import (
    ConfirmCallback,
    EmployeeCallback,
    MenuCallback,
    PaginationCallback,
    PriorityCallback,
    SettingsCallback,
    StatsCallback,
    TaskCallback,
)
from app.bot.keyboards.calendar import (
    CalendarCallback,
    TimePickerCallback,
    calendar_keyboard,
    hour_keyboard,
    minute_keyboard,
    shift_month,
)
from app.bot.keyboards.common import (
    back_inline,
    cancel_keyboard,
    main_menu_keyboard,
    reply_keyboard_remove,
    reply_remove,
    task_card_inline,
)
from app.bot.keyboards.admin import (
    admin_menu,
    confirm_inline,
    employee_select_inline,
    priority_inline,
    settings_inline,
    stats_period_inline,
    task_list_inline,
)
from app.bot.keyboards.employee import (
    employee_menu,
    my_tasks_inline,
    pagination_inline,
    profile_inline,
)

__all__ = [
    # Callback factories
    "TaskCallback",
    "EmployeeCallback",
    "PriorityCallback",
    "PaginationCallback",
    "StatsCallback",
    "SettingsCallback",
    "ConfirmCallback",
    "MenuCallback",
    "CalendarCallback",
    "TimePickerCallback",
    # Common
    "main_menu_keyboard",
    "task_card_inline",
    "cancel_keyboard",
    "back_inline",
    "reply_keyboard_remove",
    "reply_remove",
    # Admin
    "admin_menu",
    "priority_inline",
    "employee_select_inline",
    "confirm_inline",
    "task_list_inline",
    "stats_period_inline",
    "settings_inline",
    # Employee
    "employee_menu",
    "my_tasks_inline",
    "pagination_inline",
    "profile_inline",
    # Calendar & time picker
    "calendar_keyboard",
    "hour_keyboard",
    "minute_keyboard",
    "shift_month",
]
