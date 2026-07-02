"""Employee reply-menu handlers.

Each handler corresponds to one button of the employee reply menu::

    📌 My Tasks      ✅ Completed Tasks
    📅 Today         🔔 Notifications
    ⚙ Profile

The module also exposes a few small private helpers (``_resolve_employee``,
``_paginate``, ``_attach_pagination``) that are reused by the sibling
:mod:`app.bot.handlers.employee.callbacks` and
:mod:`app.bot.handlers.employee.profile` modules.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.employee import (
    my_tasks_inline,
    pagination_inline,
    profile_inline,
)
from app.models.employee import Employee
from app.models.enums import TaskStatus
from app.models.user import User
from app.notifications.templates import (
    error_message,
    no_tasks,
    not_authorized,
    profile_card,
)
from app.repositories.employee import EmployeeRepository
from app.services.task import TaskService
from app.utils.dates import remaining_time
from app.utils.formatting import divider, escape_html

if TYPE_CHECKING:
    pass

__all__ = [
    "router",
    "PER_PAGE",
    "_resolve_employee",
    "_paginate",
    "_attach_pagination",
]

router = Router(name="employee.menu")

# Inline task lists show up to this many rows per page.
PER_PAGE: int = 5


# --------------------------------------------------------------------------- #
# Shared helpers (re-used by sibling handler modules)
# --------------------------------------------------------------------------- #
async def _resolve_employee(
    user: User | None, session: AsyncSession | None
) -> Employee | None:
    """Return the :class:`Employee` linked to ``user``, or ``None``.

    The ``user.employee`` relationship is **not** eagerly loaded by the
    :class:`AuthMiddleware`, and async SQLAlchemy cannot transparently
    lazy-load it on attribute access (it raises
    ``greenlet_spawn has not been called``). We therefore ALWAYS go through
    an :class:`EmployeeRepository` lookup by ``user_id``.
    """
    if user is None or session is None:
        return None
    # NEVER access user.employee directly — it triggers a lazy-load query
    # that fails under async SQLAlchemy. Always query via the repository.
    repo = EmployeeRepository(session)
    return await repo.find_one(user_id=user.id)


def _paginate(
    items: list[Any], page: int, per_page: int = PER_PAGE
) -> tuple[list[Any], int]:
    """Slice ``items`` to the requested page.

    Args:
        items: Full ordered list.
        page: 1-based page number (clamped to the valid range).
        per_page: Page size.

    Returns:
        A ``(page_items, total_pages)`` tuple. ``total_pages`` is at least 1.
    """
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], total_pages


def _attach_pagination(
    markup: InlineKeyboardMarkup,
    page: int,
    total_pages: int,
    scope: str,
) -> InlineKeyboardMarkup:
    """Append a pagination row to ``markup`` when ``total_pages`` > 1."""
    if total_pages <= 1:
        return markup
    pg = pagination_inline(page, total_pages, scope)
    if not pg.inline_keyboard:
        return markup
    rows = list(markup.inline_keyboard) + list(pg.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --------------------------------------------------------------------------- #
# Reply-menu handlers
# --------------------------------------------------------------------------- #
@router.message(F.text == "📌 Mening vazifalarim")
async def cmd_my_tasks(
    message: Message,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """List the employee's PENDING tasks as an inline keyboard."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await message.answer(not_authorized())
            return
        tasks = await TaskService().get_employee_tasks(
            employee.id, status=TaskStatus.PENDING
        )
        if not tasks:
            await message.answer(no_tasks())
            return
        page_tasks, total_pages = _paginate(tasks, 1)
        text = (
            f"{divider()}\n"
            "📌 <b>Mening vazifalarim</b>\n"
            f"Jami: <b>{len(tasks)}</b> ta vazifa kutilmoqda\n"
            f"{divider()}"
        )
        markup = _attach_pagination(
            my_tasks_inline(page_tasks), 1, total_pages, "tasks"
        )
        await message.answer(text, reply_markup=markup)
    except Exception as exc:  # noqa: BLE001 — defensive top-level guard
        logger.exception("employee.cmd_my_tasks: {}", exc)
        await message.answer(error_message())


@router.message(F.text == "✅ Bajarilganlar")
async def cmd_completed_tasks(
    message: Message,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """List the employee's COMPLETED tasks (with an EXPIRED summary)."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await message.answer(not_authorized())
            return
        completed = await TaskService().get_employee_tasks(
            employee.id, status=TaskStatus.COMPLETED
        )
        expired = await TaskService().get_employee_tasks(
            employee.id, status=TaskStatus.EXPIRED
        )
        if not completed and not expired:
            await message.answer(no_tasks())
            return
        text_lines: list[str] = [
            divider(),
            "✅ <b>Bajarilgan vazifalar</b>",
        ]
        if completed:
            text_lines.append(f"✅ Bajarilgan: <b>{len(completed)}</b> ta")
        if expired:
            text_lines.append(f"❌ Muddati o'tgan: <b>{len(expired)}</b> ta")
        text_lines.append(divider())
        text = "\n".join(text_lines)

        page_tasks, total_pages = _paginate(completed, 1)
        markup = _attach_pagination(
            my_tasks_inline(page_tasks), 1, total_pages, "completed"
        )
        await message.answer(text, reply_markup=markup)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cmd_completed_tasks: {}", exc)
        await message.answer(error_message())


@router.message(F.text == "📅 Bugun")
async def cmd_today(
    message: Message,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """List the employee's tasks whose deadline falls within today."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await message.answer(not_authorized())
            return
        tasks = await TaskService().get_today_tasks(employee.id)
        if not tasks:
            await message.answer(no_tasks())
            return
        text_lines: list[str] = [divider(), "📅 <b>Bugungi vazifalar</b>"]
        for task in tasks[:PER_PAGE]:
            rem = remaining_time(task.deadline)
            title_raw = task.title or ""
            if len(title_raw) > 50:
                title_raw = title_raw[:47] + "..."
            text_lines.append(
                f"• #{task.id} {escape_html(title_raw)} — <i>{escape_html(rem)}</i>"
            )
        text_lines.append(divider())
        text = "\n".join(text_lines)
        page_tasks, total_pages = _paginate(tasks, 1)
        markup = _attach_pagination(
            my_tasks_inline(page_tasks), 1, total_pages, "today"
        )
        await message.answer(text, reply_markup=markup)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cmd_today: {}", exc)
        await message.answer(error_message())


@router.message(F.text == "🔔 Eslatmalar")
async def cmd_notifications(
    message: Message,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Show upcoming deadlines (next 5 PENDING tasks sorted by deadline)."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await message.answer(not_authorized())
            return
        tasks = await TaskService().get_employee_tasks(
            employee.id, status=TaskStatus.PENDING
        )
        text_lines: list[str] = [divider(), "🔔 <b>Yangi eslatmalar</b>"]
        if not tasks:
            text_lines.append("Hozircha yangi eslatmalar yo'q.")
        else:
            upcoming = tasks[:PER_PAGE]
            text_lines.append(
                f"⏳ Muddati yaqinlashayotgan <b>{len(upcoming)}</b> ta vazifa:"
            )
            for task in upcoming:
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
        markup = my_tasks_inline(tasks[:PER_PAGE]) if tasks else None
        await message.answer(text, reply_markup=markup)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cmd_notifications: {}", exc)
        await message.answer(error_message())


@router.message(F.text == "⚙ Profil")
async def cmd_profile(
    message: Message,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Render the employee's profile card with quick-action inline buttons."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None or user is None:
            await message.answer(not_authorized())
            return
        text = profile_card(user, employee)
        await message.answer(text, reply_markup=profile_inline())
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cmd_profile: {}", exc)
        await message.answer(error_message())


# --------------------------------------------------------------------------- #
# Legacy English menu buttons — send the new Uzbek keyboard so the user
# migrates automatically without needing to /start again.
# --------------------------------------------------------------------------- #
from app.bot.keyboards.employee import employee_menu as _employee_menu

_LEGACY_EMPLOYEE_BUTTONS: set[str] = {
    "📌 My Tasks",
    "✅ Completed Tasks",
    "📅 Today",
    "🔔 Notifications",
    "⚙ Profile",
    "⚙️ Profile",
}


@router.message(
    F.text.in_(_LEGACY_EMPLOYEE_BUTTONS),
)
async def legacy_employee_button(
    message: Message,
    user: User | None = None,
) -> None:
    """Handle legacy English menu buttons by re-sending the Uzbek keyboard."""
    await message.answer(
        "🔄 Menyu yangilandi — endi o'zbekcha.\n"
        "👇 Quyidagi tugmalardan foydalaning:",
        reply_markup=_employee_menu(),
    )
