"""Employee-facing reply & inline keyboards.

Employee reply menu (EXACT layout):

    📌 My Tasks      ✅ Completed Tasks
    📅 Today         🔔 Notifications
    ⚙ Profile

Inline builders:
- :func:`employee_menu`         — the persistent employee reply menu
- :func:`cancel_keyboard`       — single ❌ Cancel reply button
- :func:`my_tasks_inline`       — compact list of the employee's tasks
- :func:`pagination_inline`     — ‹ Prev / Next › pagination row
- :func:`profile_inline`        — quick profile actions (notifications, ...)
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
    MenuCallback,
    PaginationCallback,
    TaskCallback,
)
from app.models.enums import TaskPriority

if TYPE_CHECKING:
    from app.models.task import Task

__all__ = [
    "employee_menu",
    "cancel_keyboard",
    "my_tasks_inline",
    "pagination_inline",
    "profile_inline",
]


# --------------------------------------------------------------------------- #
# Reply menu
# --------------------------------------------------------------------------- #
def employee_menu() -> ReplyKeyboardMarkup:
    """Build the persistent employee reply menu (Uzbek).

    Layout (3 rows, 2 buttons per row except the last):

        📌 Mening vazifalarim   ✅ Bajarilganlar
        📅 Bugun                🔔 Eslatmalar
        ⚙ Profil
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Mening vazifalarim"),
                KeyboardButton(text="✅ Bajarilganlar"),
            ],
            [
                KeyboardButton(text="📅 Bugun"),
                KeyboardButton(text="🔔 Eslatmalar"),
            ],
            [
                KeyboardButton(text="⚙ Profil"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Xodim paneli — amalni tanlang",
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
def my_tasks_inline(tasks: Iterable["Task"]) -> InlineKeyboardMarkup:
    """Build a vertical list of the employee's tasks (one button per row).

    Each button shows the priority emoji + title and carries the task id.
    """
    builder = InlineKeyboardBuilder()
    for task in tasks:
        emoji = task.priority.emoji if isinstance(task.priority, TaskPriority) else "•"
        title = task.title if len(task.title) <= 60 else task.title[:57] + "..."
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} #{task.id} {title}",
                callback_data=TaskCallback(
                    action="view", task_id=str(task.id)
                ).pack(),
            )
        )
    return builder.as_markup()


def pagination_inline(
    page: int, total_pages: int, scope: str
) -> InlineKeyboardMarkup:
    """Build a pagination row for a list view.

    Args:
        page: Current page (1-based).
        total_pages: Total number of pages.
        scope: Listing context forwarded to the handler (e.g. ``"tasks"``,
            ``"completed"``, ``"search"``).

    The previous button is omitted on page 1, the next button on the last
    page; if there is only one page, an empty (placeholder) markup is returned
    so the caller can decide whether to attach it.
    """
    has_prev = page > 1
    has_next = page < total_pages
    if not has_prev and not has_next:
        return InlineKeyboardMarkup(inline_keyboard=[])

    row: list[InlineKeyboardButton] = []
    if has_prev:
        row.append(
            InlineKeyboardButton(
                text="‹ Prev",
                callback_data=PaginationCallback(
                    page=str(page - 1), scope=scope
                ).pack(),
            )
        )
    row.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data=PaginationCallback(page=str(page), scope=scope).pack(),
        )
    )
    if has_next:
        row.append(
            InlineKeyboardButton(
                text="Next ›",
                callback_data=PaginationCallback(
                    page=str(page + 1), scope=scope
                ).pack(),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[row])


def profile_inline() -> InlineKeyboardMarkup:
    """Build a small inline keyboard of profile actions."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 Notifications",
                    callback_data=MenuCallback(action="notifications").pack(),
                ),
                InlineKeyboardButton(
                    text="📊 My Stats",
                    callback_data=MenuCallback(action="my_stats").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="‹ Back",
                    callback_data=MenuCallback(action="back").pack(),
                )
            ],
        ]
    )
