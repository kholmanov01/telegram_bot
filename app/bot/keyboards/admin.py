"""Admin-facing reply & inline keyboards.

Admin reply menu (EXACT layout):

    ➕ New Task   👥 Employees
    📋 All Tasks  📈 Statistics
    ⚙ Settings

Inline builders:
- :func:`priority_inline`           — 4 priority picker buttons
- :func:`employee_select_inline`    — pick an employee from a list
- :func:`confirm_inline`            — ✅ Confirm / ❌ Cancel
- :func:`task_list_inline`          — compact list of tasks (one row each)
- :func:`stats_period_inline`       — stats period picker
- :func:`settings_inline`           — settings menu
- :func:`admin_menu`                — the persistent admin reply menu
- :func:`cancel_keyboard`           — single ❌ Cancel reply button
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    ConfirmCallback,
    EmployeeCallback,
    PriorityCallback,
    SettingsCallback,
    StatsCallback,
    TaskCallback,
)
from app.models.enums import TaskPriority

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.task import Task

__all__ = [
    "admin_menu",
    "cancel_keyboard",
    "priority_inline",
    "employee_select_inline",
    "confirm_inline",
    "task_list_inline",
    "stats_period_inline",
    "settings_inline",
]


# --------------------------------------------------------------------------- #
# Reply menu
# --------------------------------------------------------------------------- #
def admin_menu() -> ReplyKeyboardMarkup:
    """Build the persistent admin reply menu (Uzbek).

    Layout (3 rows, 2 buttons per row except the last):

        ➕ Yangi vazifa   👥 Xodimlar
        📋 Barcha vazifalar  📈 Statistika
        ⚙ Sozlamalar
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Yangi vazifa"),
                KeyboardButton(text="👥 Xodimlar"),
            ],
            [
                KeyboardButton(text="📋 Barcha vazifalar"),
                KeyboardButton(text="📈 Statistika"),
            ],
            [
                KeyboardButton(text="⚙ Sozlamalar"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Admin panel — amalni tanlang",
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Return a small reply keyboard with a single ``❌ Bekor qilish`` button."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
        is_persistent=False,
    )


# --------------------------------------------------------------------------- #
# Inline keyboards
# --------------------------------------------------------------------------- #
def priority_inline() -> InlineKeyboardMarkup:
    """Return the 4-button priority picker (low / medium / high / urgent)."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for priority in TaskPriority:
        row.append(
            InlineKeyboardButton(
                text=f"{priority.emoji} {priority.label}",
                callback_data=PriorityCallback(priority=priority.value).pack(),
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def employee_select_inline(employees: Iterable["Employee"]) -> InlineKeyboardMarkup:
    """Build a vertical list of employees to pick from.

    Each button carries the employee id and shows the code + full name. A
    trailing ``👥 Hamma xodimlarga`` button is added so the admin can
    broadcast the task to every active employee in one click.

    Args:
        employees: Any iterable of :class:`Employee` instances.
    """
    from app.bot.keyboards.callbacks import MenuCallback

    builder = InlineKeyboardBuilder()
    for emp in employees:
        builder.row(
            InlineKeyboardButton(
                text=f"{emp.code} — {emp.full_name}",
                callback_data=EmployeeCallback(
                    action="view", employee_id=str(emp.id)
                ).pack(),
            )
        )
    # Bottom button: broadcast to ALL active employees.
    builder.row(
        InlineKeyboardButton(
            text="👥 Hamma xodimlarga yuborish",
            callback_data=MenuCallback(action="assign_all_employees").pack(),
        )
    )
    return builder.as_markup()


def confirm_inline(payload: str) -> InlineKeyboardMarkup:
    """Return a two-button confirmation row.

    Args:
        payload: Opaque string carried through the confirmation flow
            (e.g. ``"archive:42"``). It is forwarded unchanged to the handler.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Confirm",
                    callback_data=ConfirmCallback(action="yes", payload=payload).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data=ConfirmCallback(action="no", payload=payload).pack(),
                ),
            ]
        ]
    )


def task_list_inline(tasks: Iterable["Task"]) -> InlineKeyboardMarkup:
    """Build a vertical list of tasks (one button per row).

    Each button shows the status emoji + priority emoji + title and carries
    the task id. Status emojis: ⏳ pending, ✅ completed, ❌ expired, 📦 archived.
    """
    from app.models.enums import TaskPriority, TaskStatus

    _STATUS_EMOJI = {
        TaskStatus.PENDING: "⏳",
        TaskStatus.COMPLETED: "✅",
        TaskStatus.EXPIRED: "❌",
        TaskStatus.ARCHIVED: "📦",
    }

    builder = InlineKeyboardBuilder()
    for task in tasks:
        priority = task.priority
        emoji = priority.emoji if isinstance(priority, TaskPriority) else "•"
        status_emoji = _STATUS_EMOJI.get(
            task.status if isinstance(task.status, TaskStatus) else TaskStatus(task.status),
            "•",
        )
        title = task.title if len(task.title) <= 50 else task.title[:47] + "..."
        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} {emoji} #{task.id} {title}",
                callback_data=TaskCallback(
                    action="view", task_id=str(task.id)
                ).pack(),
            )
        )
    return builder.as_markup()


def task_filter_inline() -> InlineKeyboardMarkup:
    """Status-filter buttons for the All Tasks view.

    Each button carries a :class:`MenuCallback` whose ``action`` encodes the
    filter (``filter_status_<status>``).
    """
    from app.bot.keyboards.callbacks import MenuCallback

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏳ Kutilmoqda",
                    callback_data=MenuCallback(action="filter_status_pending").pack(),
                ),
                InlineKeyboardButton(
                    text="✅ Bajarilgan",
                    callback_data=MenuCallback(action="filter_status_completed").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Muddati o'tgan",
                    callback_data=MenuCallback(action="filter_status_expired").pack(),
                ),
                InlineKeyboardButton(
                    text="📦 Arxiv",
                    callback_data=MenuCallback(action="filter_status_archived").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Hammasi",
                    callback_data=MenuCallback(action="filter_status_all").pack(),
                ),
            ],
        ]
    )


def stats_period_inline() -> InlineKeyboardMarkup:
    """Return the statistics period picker (5 buttons in a 2-column grid)."""
    periods: list[tuple[str, str]] = [
        ("daily", "📅 Daily"),
        ("weekly", "🗓 Weekly"),
        ("monthly", "📆 Monthly"),
        ("overall", "📊 Overall"),
        ("employee", "👤 By Employee"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for value, label in periods:
        row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=StatsCallback(period=value).pack(),
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_inline() -> InlineKeyboardMarkup:
    """Return the settings menu inline keyboard.

    Exposes the working-hours editor (``working_hours_start`` /
    ``working_hours_end``) and a generic ``back`` action. Concrete settings
    keys can be added as the project grows.
    """
    rows = [
        [
            InlineKeyboardButton(
                text="🕘 Working Hours Start",
                callback_data=SettingsCallback(
                    action="set", key="working_hours_start"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="🕚 Working Hours End",
                callback_data=SettingsCallback(
                    action="set", key="working_hours_end"
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌍 Timezone",
                callback_data=SettingsCallback(
                    action="set", key="app_timezone"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="🔤 Default Language",
                callback_data=SettingsCallback(
                    action="set", key="default_language"
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="‹ Back",
                callback_data=SettingsCallback(action="back", key="root").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
