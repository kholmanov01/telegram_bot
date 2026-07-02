"""Employee pagination & menu-navigation callbacks.

Renders the appropriate slice of an employee task list when the user clicks
a ``‹ Prev`` / ``Next ›`` pagination button. Also handles the ``back`` menu
navigation action.

Pagination scopes (matching :class:`PaginationCallback.scope`):

- ``"tasks"``     — the employee's PENDING tasks (from ``📌 My Tasks``).
- ``"completed"`` — the employee's COMPLETED tasks (from ``✅ Completed Tasks``).
- ``"today"``     — tasks whose deadline falls within today (from ``📅 Today``).
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.employee.menu import (
    _attach_pagination,
    _paginate,
    _resolve_employee,
)
from app.bot.keyboards.callbacks import MenuCallback, PaginationCallback
from app.bot.keyboards.employee import employee_menu, my_tasks_inline
from app.models.enums import TaskStatus
from app.models.user import User
from app.notifications.templates import (
    error_message,
    no_tasks,
    not_authorized,
)
from app.services.task import TaskService
from app.utils.dates import remaining_time
from app.utils.formatting import divider, escape_html

router = Router(name="employee.callbacks")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _editable_message(callback: CallbackQuery) -> Message | None:
    """Return the underlying editable :class:`Message`, or ``None``."""
    return callback.message if isinstance(callback.message, Message) else None


async def _safe_edit(
    callback: CallbackQuery, text: str, reply_markup: Any = None
) -> bool:
    """Edit the callback's message, ignoring benign "not modified" errors."""
    message = _editable_message(callback)
    if message is None:
        return False
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise
    return True


# --------------------------------------------------------------------------- #
# Pagination handlers
# --------------------------------------------------------------------------- #
@router.callback_query(PaginationCallback.filter(F.scope == "tasks"))
async def cb_paginate_tasks(
    callback: CallbackQuery,
    callback_data: PaginationCallback,
    user: User | None = None,
    session: AsyncSession | None = None,  # noqa: ARG001 — injected by mw
) -> None:
    """Re-render a page of the employee's PENDING task list."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await callback.answer(not_authorized(), show_alert=True)
            return
        page = int(callback_data.page)
        tasks = await TaskService().get_employee_tasks(
            employee.id, status=TaskStatus.PENDING
        )
        if not tasks:
            await _safe_edit(callback, no_tasks())
            await callback.answer()
            return
        page_tasks, total_pages = _paginate(tasks, page)
        text = (
            f"{divider()}\n"
            "📌 <b>Mening vazifalarim</b>\n"
            f"Jami: <b>{len(tasks)}</b> ta vazifa kutilmoqda\n"
            f"{divider()}"
        )
        markup = _attach_pagination(
            my_tasks_inline(page_tasks), page, total_pages, "tasks"
        )
        await _safe_edit(callback, text, reply_markup=markup)
        await callback.answer()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_paginate_tasks: {}", exc)
        await callback.answer(error_message(), show_alert=True)


@router.callback_query(PaginationCallback.filter(F.scope == "completed"))
async def cb_paginate_completed(
    callback: CallbackQuery,
    callback_data: PaginationCallback,
    user: User | None = None,
    session: AsyncSession | None = None,  # noqa: ARG001 — injected by mw
) -> None:
    """Re-render a page of the employee's COMPLETED task list."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await callback.answer(not_authorized(), show_alert=True)
            return
        page = int(callback_data.page)
        tasks = await TaskService().get_employee_tasks(
            employee.id, status=TaskStatus.COMPLETED
        )
        if not tasks:
            await _safe_edit(callback, no_tasks())
            await callback.answer()
            return
        page_tasks, total_pages = _paginate(tasks, page)
        text = (
            f"{divider()}\n"
            "✅ <b>Bajarilgan vazifalar</b>\n"
            f"Jami: <b>{len(tasks)}</b> ta vazifa bajarilgan\n"
            f"{divider()}"
        )
        markup = _attach_pagination(
            my_tasks_inline(page_tasks), page, total_pages, "completed"
        )
        await _safe_edit(callback, text, reply_markup=markup)
        await callback.answer()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_paginate_completed: {}", exc)
        await callback.answer(error_message(), show_alert=True)


@router.callback_query(PaginationCallback.filter(F.scope == "today"))
async def cb_paginate_today(
    callback: CallbackQuery,
    callback_data: PaginationCallback,
    user: User | None = None,
    session: AsyncSession | None = None,  # noqa: ARG001 — injected by mw
) -> None:
    """Re-render a page of the employee's today task list."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await callback.answer(not_authorized(), show_alert=True)
            return
        page = int(callback_data.page)
        tasks = await TaskService().get_today_tasks(employee.id)
        if not tasks:
            await _safe_edit(callback, no_tasks())
            await callback.answer()
            return
        page_tasks, total_pages = _paginate(tasks, page)
        text_lines: list[str] = [divider(), "📅 <b>Bugungi vazifalar</b>"]
        for task in page_tasks:
            rem = remaining_time(task.deadline)
            title_raw = task.title or ""
            if len(title_raw) > 50:
                title_raw = title_raw[:47] + "..."
            text_lines.append(
                f"• #{task.id} {escape_html(title_raw)} — "
                f"<i>{escape_html(rem)}</i>"
            )
        text_lines.append(divider())
        text = "\n".join(text_lines)
        markup = _attach_pagination(
            my_tasks_inline(page_tasks), page, total_pages, "today"
        )
        await _safe_edit(callback, text, reply_markup=markup)
        await callback.answer()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_paginate_today: {}", exc)
        await callback.answer(error_message(), show_alert=True)


# --------------------------------------------------------------------------- #
# Menu navigation
# --------------------------------------------------------------------------- #
@router.callback_query(MenuCallback.filter(F.action == "back"))
async def cb_menu_back(
    callback: CallbackQuery,
    callback_data: MenuCallback,  # noqa: ARG001 — needed for filter
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Return to the employee menu — show a friendly greeting + reply menu."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None or user is None:
            await callback.answer(not_authorized(), show_alert=True)
            return
        name = employee.full_name or user.first_name or "xodim"
        text = (
            f"{divider()}\n"
            f"👋 Xush kelibsiz, <b>{escape_html(name)}</b>!\n"
            "Kerakli amalni menyudan tanlang.\n"
            f"{divider()}"
        )
        # Edit the inline-bearing message back to a plain greeting (the
        # reply menu is persistent and stays on screen for the next reply).
        await _safe_edit(callback, text, reply_markup=None)
        # Re-send the reply menu in case it was replaced earlier.
        message = _editable_message(callback)
        if message is not None:
            await message.answer("👇", reply_markup=employee_menu())
        await callback.answer()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_menu_back: {}", exc)
        await callback.answer(error_message(), show_alert=True)
