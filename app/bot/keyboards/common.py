"""Shared keyboards used by both admin and employee interfaces.

Exposes:
- :func:`main_menu_keyboard` — pick the right reply menu for a role.
- :func:`task_card_inline`  — inline buttons shown under a task card.
- :func:`cancel_keyboard`   — generic "cancel" reply keyboard.
- :func:`back_inline`       — single "‹ Back" inline button.
"""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.bot.keyboards.callbacks import (
    AttachmentCallback,
    MenuCallback,
    TaskCallback,
)
from app.models.enums import UserRole

__all__ = [
    "main_menu_keyboard",
    "task_card_inline",
    "cancel_keyboard",
    "back_inline",
    "reply_keyboard_remove",
    "reply_remove",
]


# --------------------------------------------------------------------------- #
# Reply (menu) keyboards
# --------------------------------------------------------------------------- #
def main_menu_keyboard(role: UserRole) -> ReplyKeyboardMarkup:
    """Return the persistent reply menu for the given role.

    Args:
        role: The :class:`UserRole` of the authenticated user.

    Returns:
        A resized, persistent reply keyboard with the appropriate buttons.
    """
    # Imported lazily to avoid a circular import (admin/employee modules
    # import from this module via :data:`__all__`).
    from app.bot.keyboards.admin import admin_menu
    from app.bot.keyboards.employee import employee_menu

    if role == UserRole.SUPER_ADMIN:
        return admin_menu()
    return employee_menu()


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Return a small reply keyboard with a single ``❌ Bekor qilish`` button."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
        is_persistent=False,
    )


# Alias kept for symmetry with admin/employee modules.
reply_keyboard_remove: ReplyKeyboardRemove = ReplyKeyboardRemove()
reply_remove: ReplyKeyboardRemove = ReplyKeyboardRemove()


# --------------------------------------------------------------------------- #
# Inline keyboards
# --------------------------------------------------------------------------- #
def task_card_inline(
    task_id: int,
    viewer_is_employee: bool,
    attachment_count: int = 0,
) -> InlineKeyboardMarkup:
    """Build the inline keyboard shown under a task card.

    Employees get ``✅ Completed`` and ``📝 View Details``. Admins additionally
    get ``📦 Archive`` (or ``♻ Restore`` — the handler decides which to show
    based on the task status, here we expose both as separate buttons the
    handler can filter out by status when needed; to keep the card uncluttered
    we only include ``📦 Archive`` for admins and rely on the details view for
    the restore action).

    A third row is always appended with a ``📎 Fayllar`` button showing the
    number of attached files (when ``attachment_count > 0``).

    Args:
        task_id: Primary key of the task.
        viewer_is_employee: ``True`` if the viewer is the assignee.
        attachment_count: Number of attachments currently linked to the task.
            When greater than zero the count is shown inside the button label.

    Returns:
        An :class:`InlineKeyboardMarkup` with two or three rows of buttons.
    """
    tid = str(task_id)
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="✅ Completed",
                callback_data=TaskCallback(action="complete", task_id=tid).pack(),
            ),
            InlineKeyboardButton(
                text="📝 View Details",
                callback_data=TaskCallback(action="details", task_id=tid).pack(),
            ),
        ]
    ]
    if not viewer_is_employee:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📦 Archive",
                    callback_data=TaskCallback(action="archive", task_id=tid).pack(),
                ),
                InlineKeyboardButton(
                    text="♻ Restore",
                    callback_data=TaskCallback(action="restore", task_id=tid).pack(),
                ),
            ]
        )

    files_label = "📎 Fayllar"
    if attachment_count > 0:
        files_label = f"📎 Fayllar ({attachment_count})"
    rows.append(
        [
            InlineKeyboardButton(
                text=files_label,
                callback_data=AttachmentCallback(
                    action="view", task_id=tid
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_inline(action: str = "back") -> InlineKeyboardMarkup:
    """Return a single ``‹ Back`` inline button using :class:`MenuCallback`."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="‹ Back",
                    callback_data=MenuCallback(action=action).pack(),
                )
            ]
        ]
    )
