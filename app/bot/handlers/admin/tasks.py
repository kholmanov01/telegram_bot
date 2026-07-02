"""Admin task views: filters, details, archive/restore, search, export.

Covers:

- ``TaskCallback(action="view")``    — render the task card with admin inline.
- ``TaskCallback(action="details")`` — render the full card + task-log history.
- ``TaskCallback(action="archive")`` — archive the task.
- ``TaskCallback(action="restore")`` — restore an archived task.
- ``MenuCallback(action="search_tasks")``          — start the search FSM.
- ``TaskSearchStates.waiting_query`` message       — execute the search.
- ``MenuCallback(action="export_tasks_excel|pdf")`` — download the dataset.
"""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.types.input_file import BufferedInputFile
from loguru import logger

from app.bot.keyboards.admin import (
    admin_menu,
    cancel_keyboard,
    task_filter_inline,
    task_list_inline,
)
from app.bot.keyboards.callbacks import MenuCallback, TaskCallback
from app.bot.keyboards.common import task_card_inline
from app.bot.states.task import TaskSearchStates
from app.database.session import get_session
from app.models.enums import TaskStatus
from app.models.task_log import TaskLog
from app.notifications.templates import (
    error_message,
    no_tasks,
    task_archived,
    task_restored,
)
from app.repositories.attachment import AttachmentRepository
from app.repositories.task_log import TaskLogRepository
from app.services.attachment import AttachmentService
from app.services.export import ExportService
from app.services.task import TaskService
from app.utils.dates import format_datetime
from app.utils.formatting import escape_html, task_card
from app.utils.security import sanitize_text

router = Router(name="admin.tasks")


# --------------------------------------------------------------------------- #
# Task view / details / archive / restore
# --------------------------------------------------------------------------- #
@router.callback_query(TaskCallback.filter(F.action == "view"))
async def task_view(
    callback: CallbackQuery,
    callback_data: TaskCallback,
) -> None:
    """Render a single task card with the admin inline keyboard."""
    try:
        task_id = int(callback_data.task_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri vazifa.", show_alert=True)
        return

    task = await TaskService().get_task(task_id)
    if task is None:
        await callback.answer("Vazifa topilmadi.", show_alert=True)
        return

    try:
        attachment_count = await AttachmentService().get_attachment_count(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning("task_view: attachment count failed: {}", exc)
        attachment_count = 0

    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            task_card(task, employee=getattr(task, "employee", None)),
            reply_markup=task_card_inline(
                task.id,
                viewer_is_employee=False,
                attachment_count=attachment_count,
            ),
        )
    await callback.answer()


@router.callback_query(TaskCallback.filter(F.action == "details"))
async def task_details(
    callback: CallbackQuery,
    callback_data: TaskCallback,
) -> None:
    """Render the task card plus a task-log history block."""
    try:
        task_id = int(callback_data.task_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri vazifa.", show_alert=True)
        return

    task = await TaskService().get_task(task_id)
    if task is None:
        await callback.answer("Vazifa topilmadi.", show_alert=True)
        return

    # Fetch the task log entries and attachment summary via a short-lived
    # session so the card has the latest history + attachment count.
    logs: list[TaskLog] = []
    attachment_count = 0
    attachment_types: list[str] = []
    try:
        async with get_session() as session:
            log_repo = TaskLogRepository(session)
            logs = await log_repo.get_for_task(task_id)

            att_repo = AttachmentRepository(session)
            attachments = await att_repo.get_for_task(task_id)
            attachment_count = len(attachments)
            # Preserve insertion order while deduplicating types.
            seen: set[str] = set()
            for att in attachments:
                if att.file_type and att.file_type not in seen:
                    seen.add(att.file_type)
                    attachment_types.append(att.file_type)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning("Failed to load task logs for {}: {}", task_id, exc)

    history_lines: list[str] = ["\n\n📜 <b>Tarix</b>"]
    if not logs:
        history_lines.append("—")
    else:
        for log in logs[-15:]:  # show last 15 entries
            occurred = format_datetime(log.occurred_at)
            action = escape_html(log.action)
            msg = escape_html(log.message or "")
            transition = ""
            if log.from_status or log.to_status:
                transition = (
                    f" ({escape_html(log.from_status or '—')} → "
                    f"{escape_html(log.to_status or '—')})"
                )
            history_lines.append(
                f"• [{occurred}] <b>{action}</b>{transition}"
                + (f" — {msg}" if msg else "")
            )

    # Append a compact attachment summary to the card body.
    attachment_summary = ""
    if attachment_count > 0:
        types_str = ", ".join(escape_html(t) for t in attachment_types)
        attachment_summary = (
            f"\n\n📎 <b>Biriktirilgan fayllar:</b> {attachment_count} ta"
            + (f" <i>({types_str})</i>" if types_str else "")
        )

    text = task_card(
        task, employee=getattr(task, "employee", None)
    ) + "\n".join(history_lines) + attachment_summary

    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            text,
            reply_markup=task_card_inline(
                task.id,
                viewer_is_employee=False,
                attachment_count=attachment_count,
            ),
        )
    await callback.answer()


@router.callback_query(TaskCallback.filter(F.action == "archive"))
async def task_archive(
    callback: CallbackQuery,
    callback_data: TaskCallback,
) -> None:
    """Archive a task."""
    try:
        task_id = int(callback_data.task_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri vazifa.", show_alert=True)
        return

    try:
        await TaskService().archive_task(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to archive task {}: {}", task_id, exc)
        await callback.answer("Xatolik.", show_alert=True)
        return

    message = callback.message
    if isinstance(message, Message):
        await message.answer(task_archived())
    await callback.answer("✅ Arxivlandi.")


@router.callback_query(TaskCallback.filter(F.action == "restore"))
async def task_restore(
    callback: CallbackQuery,
    callback_data: TaskCallback,
) -> None:
    """Restore a previously archived task."""
    try:
        task_id = int(callback_data.task_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri vazifa.", show_alert=True)
        return

    try:
        await TaskService().restore_task(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to restore task {}: {}", task_id, exc)
        await callback.answer("Xatolik.", show_alert=True)
        return

    message = callback.message
    if isinstance(message, Message):
        await message.answer(task_restored())
    await callback.answer("✅ Qaytarildi.")


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
@router.callback_query(
    MenuCallback.filter(F.action == "search_tasks"),
    StateFilter(None),
)
async def start_search(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Enter the search FSM and ask for a query string."""
    await state.clear()
    await state.set_state(TaskSearchStates.waiting_query)
    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            "🔍 Qidirish so'zini kiriting (vazifa sarlavhasi yoki ta'rifi bo'yicha):",
            reply_markup=cancel_keyboard(),
        )
    await callback.answer()


@router.message(
    StateFilter(TaskSearchStates.waiting_query),
    F.text,
)
async def run_search(message: Message, state: FSMContext) -> None:
    """Execute the task search and render the matching list."""
    query = sanitize_text(message.text or "")
    if not query:
        await message.answer("⚠️ So'z bo'sh bo'lishi mumkin emas. Qaytadan kiriting.")
        return

    try:
        tasks = await TaskService().search_tasks(query, limit=50)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Search failed: {}", exc)
        await state.clear()
        await message.answer(error_message(), reply_markup=admin_menu())
        return

    await state.clear()
    if not tasks:
        await message.answer(
            no_tasks() + f"\n🔍 Qidiruv: <code>{escape_html(query)}</code>",
            reply_markup=admin_menu(),
        )
        return

    await message.answer(
        f"🔍 <b>Qidiruv natijasi:</b> {len(tasks)} ta vazifa topildi.",
        reply_markup=task_list_inline(tasks),
    )
    await message.answer(
        "Bosh menyu:", reply_markup=admin_menu()
    )


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
@router.callback_query(
    MenuCallback.filter(F.action == "export_tasks_excel"),
)
async def export_tasks_excel(callback: CallbackQuery) -> None:
    """Build and send an ``.xlsx`` document with all tasks."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    await callback.answer("⏳ Tayyorlanmoqda...")
    try:
        data = await ExportService().export_tasks_excel()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Excel export failed: {}", exc)
        await message.answer(error_message())
        return

    await message.answer_document(
        document=BufferedInputFile(
            data, filename=f"tasks_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
        ),
        caption="📊 Vazifalar hisoboti (Excel)",
    )


@router.callback_query(
    MenuCallback.filter(F.action == "export_tasks_pdf"),
)
async def export_tasks_pdf(callback: CallbackQuery) -> None:
    """Build and send a PDF document with all tasks."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    await callback.answer("⏳ Tayyorlanmoqda...")
    try:
        data = await ExportService().export_tasks_pdf()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("PDF export failed: {}", exc)
        await message.answer(error_message())
        return

    await message.answer_document(
        document=BufferedInputFile(
            data, filename=f"tasks_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        ),
        caption="📄 Vazifalar hisoboti (PDF)",
    )


# --------------------------------------------------------------------------- #
# Status filter — show tasks filtered by status (pending/completed/expired/archived/all)
# --------------------------------------------------------------------------- #
_STATUS_MAP: dict[str, TaskStatus | None] = {
    "filter_status_pending": TaskStatus.PENDING,
    "filter_status_completed": TaskStatus.COMPLETED,
    "filter_status_expired": TaskStatus.EXPIRED,
    "filter_status_archived": TaskStatus.ARCHIVED,
    "filter_status_all": None,
}

_STATUS_LABELS: dict[str, str] = {
    "filter_status_pending": "⏳ Kutilmoqda",
    "filter_status_completed": "✅ Bajarilgan",
    "filter_status_expired": "❌ Muddati o'tgan",
    "filter_status_archived": "📦 Arxivlangan",
    "filter_status_all": "📋 Hammasi",
}


@router.callback_query(
    MenuCallback.filter(
        F.action.in_({
            "filter_status_pending",
            "filter_status_completed",
            "filter_status_expired",
            "filter_status_archived",
            "filter_status_all",
        })
    ),
)
async def filter_tasks_by_status(
    callback: CallbackQuery,
    callback_data: MenuCallback,
) -> None:
    """Filter tasks by status and re-render the list with the filter bar."""
    action = callback_data.action
    status = _STATUS_MAP.get(action)
    label = _STATUS_LABELS.get(action, "Vazifalar")

    try:
        tasks = await TaskService().get_all_filtered(
            status=status, limit=30, offset=0
        )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Filter tasks failed: {}", exc)
        await callback.answer("Xatolik.", show_alert=True)
        return

    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    filter_kb = task_filter_inline()

    if not tasks:
        try:
            await message.edit_text(
                f"{label}\n\nHech qanday vazifa topilmadi.\n\n🔽 Holat bo'yicha filtrlash:",
                reply_markup=filter_kb,
            )
        except Exception:  # noqa: BLE001 — "message not modified"
            pass
        await callback.answer()
        return

    kb = task_list_inline(tasks)
    extra = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Qidirish",
                    callback_data=MenuCallback(action="search_tasks").pack(),
                ),
                InlineKeyboardButton(
                    text="📊 Excel",
                    callback_data=MenuCallback(action="export_tasks_excel").pack(),
                ),
                InlineKeyboardButton(
                    text="📄 PDF",
                    callback_data=MenuCallback(action="export_tasks_pdf").pack(),
                ),
            ]
        ]
    )
    combined_rows = (
        list(filter_kb.inline_keyboard)
        + list(kb.inline_keyboard)
        + list(extra.inline_keyboard)
    )
    combined = InlineKeyboardMarkup(inline_keyboard=combined_rows)

    header = (
        f"{label}\n"
        f"Jami: {len(tasks)} ta vazifa\n"
        "🔽 Holat bo'yicha filtrlash:"
    )
    try:
        await message.edit_text(header, reply_markup=combined)
    except Exception:  # noqa: BLE001 — "message not modified"
        pass
    await callback.answer()


__all__ = ["router"]
