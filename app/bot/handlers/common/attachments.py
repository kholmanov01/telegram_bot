"""Common attachment handlers — view / add files to a task.

This router is mounted under the common router so it is reachable by both
super admins and employees. Because there is no role filter at the router
level, every handler performs an explicit ownership check before doing
anything: the acting user must either

- be the employee the task is assigned to (i.e. ``task.employee.user_id ==
  user.id``), OR
- be a super admin (``user.role == UserRole.SUPER_ADMIN`` or
  ``user.telegram_id in settings.super_admin_id_list``).

Unauthorized callers get a brief ``Ruxsat yo'q`` answer and the handler
returns early.
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from loguru import logger

from app.bot.keyboards.callbacks import AttachmentCallback, TaskCallback
from app.bot.keyboards.common import cancel_keyboard
from app.bot.states.task import TaskAttachmentStates
from app.config.settings import settings
from app.models.attachment import Attachment
from app.models.enums import UserRole
from app.models.task import Task
from app.models.user import User
from app.notifications.templates import error_message
from app.services.attachment import AttachmentService
from app.services.task import TaskService
from app.utils.formatting import divider, escape_html
from app.utils.telegram import extract_file_info

router = Router(name="common.attachments")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _human_size(size: int | None) -> str:
    """Return a human-readable size string (B / KB / MB / GB).

    Args:
        size: File size in bytes (or ``None``).

    Returns:
        Human-readable string, ``"—"`` when ``size`` is ``None``.
    """
    if size is None:
        return "—"
    try:
        s = float(size)
    except (TypeError, ValueError):
        return "—"
    if s < 1024:
        return f"{int(s)} B"
    if s < 1024 * 1024:
        return f"{s / 1024:.1f} KB"
    if s < 1024 * 1024 * 1024:
        return f"{s / (1024 * 1024):.1f} MB"
    return f"{s / (1024 * 1024 * 1024):.2f} GB"


_FILE_TYPE_EMOJI: dict[str, str] = {
    "photo": "🖼",
    "document": "📄",
    "video": "🎬",
    "audio": "🎵",
    "voice": "🎤",
    "animation": "🎞",
}


def _file_emoji(file_type: str | None) -> str:
    """Return an emoji for a given file_type string."""
    if not file_type:
        return "📎"
    return _FILE_TYPE_EMOJI.get(file_type.lower(), "📎")


def _is_authorized(task: Task | None, user: User | None) -> bool:
    """Return ``True`` if ``user`` may view / mutate attachments on ``task``.

    Authorized when:

    - ``user`` is a super admin (env allow-list OR DB role), OR
    - ``user`` owns the task (``task.employee.user_id == user.id``).

    Args:
        task: The task being accessed (may be ``None``).
        user: The acting user (may be ``None``).

    Returns:
        ``True`` if access is allowed.
    """
    if user is None or task is None:
        return False

    # Env-allow-listed super admins always pass.
    if user.telegram_id is not None and user.telegram_id in settings.super_admin_id_list:
        return True

    # DB-stored role.
    role = getattr(user, "role", None)
    if role == UserRole.SUPER_ADMIN or str(role).lower() == "super_admin":
        return True

    # Task ownership.
    employee = getattr(task, "employee", None)
    if employee is not None and employee.user_id == user.id:
        return True

    return False


def _attachment_list_inline(task_id: int) -> InlineKeyboardMarkup:
    """Build the inline keyboard shown on the attachment list view."""
    tid = str(task_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Fayl qo'shish",
                    callback_data=AttachmentCallback(
                        action="add", task_id=tid
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="‹ Orqaga",
                    callback_data=TaskCallback(
                        action="view", task_id=tid
                    ).pack(),
                )
            ],
        ]
    )


def _render_attachment_list(
    task_id: int, attachments: list[Attachment]
) -> str:
    """Build the HTML message body for the attachment list view."""
    lines: list[str] = [
        divider(),
        f"📎 <b>Vazifa #{task_id} fayllari</b>",
        f"<b>Jami:</b> {len(attachments)} ta",
    ]
    if not attachments:
        lines.append("")
        lines.append("<i>Hozircha biriktirilgan fayl yo'q.</i>")
    else:
        lines.append("")
        for idx, att in enumerate(attachments, start=1):
            emoji = _file_emoji(att.file_type)
            name = escape_html(att.file_name) or "—"
            size = _human_size(att.file_size)
            ftype = escape_html(att.file_type or "—")
            lines.append(
                f"{emoji} <b>{idx}.</b> {name} "
                f"<i>({ftype}, {size})</i>"
            )
    lines.append(divider())
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
@router.callback_query(AttachmentCallback.filter(F.action == "view"))
async def attachment_view(
    callback: CallbackQuery,
    callback_data: AttachmentCallback,
    user: User | None = None,
) -> None:
    """List all attachments of a task (with ownership check)."""
    try:
        task_id = int(callback_data.task_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri vazifa.", show_alert=True)
        return

    try:
        task = await TaskService().get_task(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("attachment_view: failed to load task {}: {}", task_id, exc)
        await callback.answer(error_message(), show_alert=True)
        return

    if task is None:
        await callback.answer("Vazifa topilmadi.", show_alert=True)
        return

    if not _is_authorized(task, user):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    try:
        attachments = await AttachmentService().get_task_attachments(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error(
            "attachment_view: failed to load attachments for {}: {}",
            task_id,
            exc,
        )
        attachments = []

    text = _render_attachment_list(task_id, attachments)
    markup = _attachment_list_inline(task_id)

    message = callback.message
    if isinstance(message, Message):
        try:
            await message.edit_text(text, reply_markup=markup)
        except Exception:  # noqa: BLE001 — "message not modified" etc.
            pass
    await callback.answer()


@router.callback_query(AttachmentCallback.filter(F.action == "add"))
async def attachment_add(
    callback: CallbackQuery,
    callback_data: AttachmentCallback,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Begin the add-attachment flow (ownership-checked)."""
    try:
        task_id = int(callback_data.task_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri vazifa.", show_alert=True)
        return

    try:
        task = await TaskService().get_task(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("attachment_add: failed to load task {}: {}", task_id, exc)
        await callback.answer(error_message(), show_alert=True)
        return

    if task is None:
        await callback.answer("Vazifa topilmadi.", show_alert=True)
        return

    if not _is_authorized(task, user):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    await state.set_state(TaskAttachmentStates.waiting_file)
    await state.update_data(task_id=task_id)

    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            "📎 Fayl yoki rasmni yuboring:",
            reply_markup=cancel_keyboard(),
        )
    await callback.answer()


@router.message(
    StateFilter(TaskAttachmentStates.waiting_file),
    F.photo | F.document | F.video | F.audio | F.voice | F.animation,
)
async def attachment_receive_file(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Receive a file from the user and persist it as an attachment."""
    data: dict[str, Any] = await state.get_data()
    task_id_raw = data.get("task_id")
    try:
        task_id = int(task_id_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        await message.answer(error_message())
        await state.clear()
        return

    # Re-check authorization — the user may have lost access between the
    # ``add`` callback and this message (e.g. task reassigned).
    try:
        task = await TaskService().get_task(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error(
            "attachment_receive_file: failed to load task {}: {}",
            task_id,
            exc,
        )
        await message.answer(error_message())
        await state.clear()
        return

    if task is None or not _is_authorized(task, user):
        await message.answer("🚫 Ruxsat yo'q.")
        await state.clear()
        return

    info = extract_file_info(message)
    if info is None:
        await message.answer(
            "⚠️ Fayl aniqlanmadi. Iltimos, rasm yoki fayl yuboring."
        )
        return

    uploaded_by = user.id if user is not None else None
    try:
        await AttachmentService().add_attachment(
            task_id=task_id,
            file_id=info["file_id"],
            file_unique_id=info["file_unique_id"],
            file_type=info["file_type"],
            file_name=info.get("file_name"),
            file_size=info.get("file_size"),
            caption=info.get("caption"),
            mime_type=info.get("mime_type"),
            uploaded_by=uploaded_by,
        )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to persist attachment for task {}: {}", task_id, exc)
        await message.answer(error_message())
        await state.clear()
        return

    await state.clear()
    await message.answer("✅ Fayl qo'shildi.")

    # Re-render the attachment list inline keyboard for quick follow-up.
    markup = _attachment_list_inline(task_id)
    try:
        attachments = await AttachmentService().get_task_attachments(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning(
            "attachment_receive_file: could not reload list for {}: {}",
            task_id,
            exc,
        )
        attachments = []
    text = _render_attachment_list(task_id, attachments)
    await message.answer(text, reply_markup=markup)


@router.message(
    StateFilter(TaskAttachmentStates.waiting_file),
    Command("cancel"),
)
async def attachment_cancel(
    message: Message, state: FSMContext
) -> None:
    """Cancel the add-attachment flow."""
    await state.clear()
    await message.answer("🚫 Fayl qo'shish bekor qilindi.")


@router.message(
    StateFilter(TaskAttachmentStates.waiting_file),
    F.text == "❌ Bekor qilish",
)
async def attachment_cancel_text(
    message: Message, state: FSMContext
) -> None:
    """Reply-keyboard ``❌ Cancel`` button fallback for cancelling."""
    await state.clear()
    await message.answer("🚫 Fayl qo'shish bekor qilindi.")


__all__ = ["router"]
