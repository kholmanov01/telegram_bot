"""Employee task-interaction handlers (view / complete / details).

Each handler verifies that the acting employee owns the task before showing
or modifying it — employees can only act on tasks assigned to them. The
ownership check is :func:`_owns_task`, which compares
``task.employee.user_id`` against the injected ``user.id``.
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.callbacks import TaskCallback
from app.bot.keyboards.common import task_card_inline
from app.models.task import Task
from app.models.user import User
from app.notifications.templates import (
    error_message,
    not_authorized,
    task_completed_employee,
)
from app.repositories.attachment import AttachmentRepository
from app.repositories.task_log import TaskLogRepository
from app.services.attachment import AttachmentService
from app.services.task import TaskService
from app.utils.dates import format_datetime
from app.utils.formatting import divider, escape_html, task_card

router = Router(name="employee.tasks")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _owns_task(task: Task | None, user: User | None) -> bool:
    """Return ``True`` if ``task`` is assigned to the given user's employee."""
    if user is None or task is None:
        return False
    employee = getattr(task, "employee", None)
    if employee is None:
        return False
    return employee.user_id == user.id


def _editable_message(callback: CallbackQuery) -> Message | None:
    """Return the underlying editable :class:`Message`, or ``None``.

    Callback queries on very old messages carry an ``InaccessibleMessage``
    stub instead of a real :class:`Message`; such messages cannot be edited.
    """
    return callback.message if isinstance(callback.message, Message) else None


async def _safe_edit(
    callback: CallbackQuery, text: str, reply_markup: Any = None
) -> bool:
    """Edit the callback's message, silently swallowing "not modified" errors.

    Returns ``True`` if the message was edited (or there was nothing to do),
    ``False`` if no editable message was available.
    """
    message = _editable_message(callback)
    if message is None:
        return False
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        # "message is not modified" is benign — the user re-clicked without
        # any state change.
        if "not modified" not in str(exc).lower():
            raise
    return True


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
@router.callback_query(TaskCallback.filter(F.action == "view"))
async def cb_task_view(
    callback: CallbackQuery,
    callback_data: TaskCallback,
    user: User | None = None,
    session: AsyncSession | None = None,  # noqa: ARG001 — injected by mw
) -> None:
    """Open a single task card for the acting employee."""
    try:
        task_id = int(callback_data.task_id)
        task = await TaskService().get_task(task_id)
        if task is None:
            await _safe_edit(callback, "Vazifa topilmadi.")
            await callback.answer()
            return
        if not _owns_task(task, user):
            await _safe_edit(callback, not_authorized())
            await callback.answer()
            return

        try:
            attachment_count = await AttachmentService().get_attachment_count(
                task_id
            )
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning("cb_task_view: attachment count failed: {}", exc)
            attachment_count = 0

        text = task_card(task, employee=task.employee, with_remaining=True)
        markup = task_card_inline(
            task.id,
            viewer_is_employee=True,
            attachment_count=attachment_count,
        )
        await _safe_edit(callback, text, reply_markup=markup)
        await callback.answer()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_task_view: {}", exc)
        await callback.answer(error_message(), show_alert=True)


@router.callback_query(TaskCallback.filter(F.action == "complete"))
async def cb_task_complete(
    callback: CallbackQuery,
    callback_data: TaskCallback,
    user: User | None = None,
    session: AsyncSession | None = None,  # noqa: ARG001 — injected by mw
) -> None:
    """Mark the task as COMPLETED (only the owning employee may do this)."""
    try:
        if user is None:
            await callback.answer(not_authorized(), show_alert=True)
            return
        task_id = int(callback_data.task_id)
        task = await TaskService().get_task(task_id)
        if task is None:
            await callback.answer("Vazifa topilmadi.", show_alert=True)
            return
        if not _owns_task(task, user):
            await callback.answer(not_authorized(), show_alert=True)
            return
        success, message = await TaskService().complete_task(task_id, user.id)
        if success:
            await _safe_edit(callback, task_completed_employee(), reply_markup=None)
            await callback.answer("✅ Bajarildi")
        else:
            await callback.answer(message, show_alert=True)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_task_complete: {}", exc)
        await callback.answer(error_message(), show_alert=True)


@router.callback_query(TaskCallback.filter(F.action == "details"))
async def cb_task_details(
    callback: CallbackQuery,
    callback_data: TaskCallback,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Show the full task card plus a chronological history (task logs)."""
    try:
        task_id = int(callback_data.task_id)
        task = await TaskService().get_task(task_id)
        if task is None:
            await callback.answer("Vazifa topilmadi.", show_alert=True)
            return
        if not _owns_task(task, user):
            await callback.answer(not_authorized(), show_alert=True)
            return

        # ``get_task`` uses ``get_with_relations`` which loads employee +
        # assigner but NOT logs/attachments. Query them explicitly on the
        # injected session (same transaction as the middleware).
        history_lines: list[str] = []
        attachment_count = 0
        attachment_types: list[str] = []
        if session is not None:
            log_repo = TaskLogRepository(session)
            logs = await log_repo.get_for_task(task_id)
            if logs:
                history_lines.append("")
                history_lines.append(divider())
                history_lines.append("📜 <b>Tarix</b>")
                for log in logs:
                    occurred = format_datetime(log.occurred_at) or "—"
                    message_text = log.message or log.action
                    history_lines.append(
                        f"• {escape_html(occurred)} — {escape_html(message_text)}"
                    )

            att_repo = AttachmentRepository(session)
            attachments = await att_repo.get_for_task(task_id)
            attachment_count = len(attachments)
            seen: set[str] = set()
            for att in attachments:
                if att.file_type and att.file_type not in seen:
                    seen.add(att.file_type)
                    attachment_types.append(att.file_type)

        text = task_card(task, employee=task.employee, with_remaining=True)
        if history_lines:
            text = text + "\n" + "\n".join(history_lines)
        if attachment_count > 0:
            types_str = ", ".join(escape_html(t) for t in attachment_types)
            text += (
                f"\n\n📎 <b>Biriktirilgan fayllar:</b> {attachment_count} ta"
                + (f" <i>({types_str})</i>" if types_str else "")
            )

        markup = task_card_inline(
            task.id,
            viewer_is_employee=True,
            attachment_count=attachment_count,
        )
        await _safe_edit(callback, text, reply_markup=markup)
        await callback.answer()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_task_details: {}", exc)
        await callback.answer(error_message(), show_alert=True)
