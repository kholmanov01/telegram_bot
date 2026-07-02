"""Admin reply-keyboard menu + ``/admin`` command.

Routes the admin's reply-keyboard button presses to the relevant surfaces:

- ``➕ New Task``     — start the task-creation FSM wizard.
- ``👥 Employees``    — list active employees.
- ``📋 All Tasks``    — show recent tasks with inline actions.
- ``📈 Statistics``   — show the period picker.
- ``⚙ Settings``      — show the settings menu.

Each handler is guarded with :class:`StateFilter(None)` so that pressing a
menu button mid-FSM-wizard does not accidentally start a new flow.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from app.bot.keyboards.admin import (
    admin_menu,
    cancel_keyboard,
    settings_inline,
    stats_period_inline,
    task_filter_inline,
    task_list_inline,
)
from app.bot.keyboards.callbacks import EmployeeCallback, MenuCallback
from app.bot.states.task import TaskCreationStates
from app.models.user import User
from app.notifications.templates import (
    ask_task_title,
    no_tasks,
    settings_menu,
)
from app.services.employee import EmployeeService
from app.services.task import TaskService
from app.utils.formatting import employee_card, escape_html

router = Router(name="admin.menu")


@router.message(Command("admin"), StateFilter(None))
async def cmd_admin(message: Message) -> None:
    """Show the admin welcome + menu (same as pressing any admin button)."""
    from app.notifications.templates import admin_welcome

    await message.answer(admin_welcome(), reply_markup=admin_menu())


@router.message(F.text == "➕ Yangi vazifa", StateFilter(None))
async def menu_new_task(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Begin the task-creation wizard at the title step."""
    await state.clear()
    await state.set_state(TaskCreationStates.waiting_title)
    await message.answer(ask_task_title(), reply_markup=cancel_keyboard())


@router.message(F.text == "👥 Xodimlar", StateFilter(None))
async def menu_employees(message: Message) -> None:
    """List active employees with an inline ``new`` button.

    Each employee is rendered as an inline button (``EMP001 — Ism``);
    pressing it opens the employee card with deactivate/delete actions.
    """
    try:
        employees = await EmployeeService().get_active_employees()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to load employees: {}", exc)
        from app.notifications.templates import error_message

        await message.answer(error_message())
        return

    if not employees:
        await message.answer("📭 Hozircha xodimlar yo'q.")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Yangi xodim qo'shish",
                        callback_data=EmployeeCallback(
                            action="new", employee_id="0"
                        ).pack(),
                    )
                ]
            ]
        )
        await message.answer(
            "Yangi xodim qo'shish uchun quyidagi tugmani bosing.",
            reply_markup=kb,
        )
        return

    # Build inline buttons — one per employee + "add new" at the bottom.
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for emp in employees[:30]:
        active_mark = "🟢" if emp.is_active else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{active_mark} {emp.code} — {emp.full_name[:40]}",
                callback_data=EmployeeCallback(
                    action="view", employee_id=str(emp.id)
                ).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="➕ Yangi xodim qo'shish",
            callback_data=EmployeeCallback(
                action="new", employee_id="0"
            ).pack(),
        )
    )

    header = (
        f"👥 <b>Xodimlar ro'yxati</b>\n"
        f"Jami: <b>{len(employees)}</b> ta xodim\n"
        "👇 Tafsilotlarni ko'rish uchun xodimni bosing"
    )
    await message.answer(header, reply_markup=builder.as_markup())


@router.message(F.text == "📋 Barcha vazifalar", StateFilter(None))
async def menu_all_tasks(message: Message) -> None:
    """Show recent tasks with filter + search + export inline buttons."""
    try:
        tasks = await TaskService().get_all_filtered(limit=10, offset=0)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to load tasks: {}", exc)
        from app.notifications.templates import error_message

        await message.answer(error_message())
        return

    # Always show the filter row first.
    filter_kb = task_filter_inline()

    if not tasks:
        await message.answer(
            no_tasks() + "\n\n📋 Holat bo'yicha filtrlash:",
            reply_markup=filter_kb,
        )
        return

    kb = task_list_inline(tasks)
    # Actions row.
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
    # Merge: filter row + task list + actions row.
    combined_rows = (
        list(filter_kb.inline_keyboard)
        + list(kb.inline_keyboard)
        + list(extra.inline_keyboard)
    )
    combined = InlineKeyboardMarkup(inline_keyboard=combined_rows)

    header = (
        "📋 <b>So'nggi vazifalar</b>\n"
        f"Jami ko'rsatilgan: {escape_html(str(len(tasks)))} ta\n"
        "🔽 Holat bo'yicha filtrlang:"
    )
    await message.answer(header, reply_markup=combined)


@router.message(F.text == "📈 Statistika", StateFilter(None))
async def menu_statistics(message: Message) -> None:
    """Show the statistics period picker."""
    await message.answer(
        "📈 <b>Statistika</b>\nDavrni tanlang:",
        reply_markup=stats_period_inline(),
    )


@router.message(F.text == "⚙ Sozlamalar", StateFilter(None))
async def menu_settings(message: Message) -> None:
    """Show the settings menu."""
    await message.answer(settings_menu(), reply_markup=settings_inline())


# --------------------------------------------------------------------------- #
# Legacy English menu buttons — send the new Uzbek keyboard so the user
# migrates automatically without needing to /start again.
# --------------------------------------------------------------------------- #
_LEGACY_ADMIN_BUTTONS: dict[str, str] = {
    "➕ New Task": "➕ Yangi vazifa",
    "👥 Employees": "👥 Xodimlar",
    "📋 All Tasks": "📋 Barcha vazifalar",
    "📈 Statistics": "📈 Statistika",
    "⚙ Settings": "⚙ Sozlamalar",
    "📊 Statistics": "📈 Statistika",  # emoji variant
    "⚙️ Settings": "⚙ Sozlamalar",
}


@router.message(
    F.text.in_(set(_LEGACY_ADMIN_BUTTONS.keys())),
    StateFilter(None),
)
async def legacy_admin_button(message: Message) -> None:
    """Handle legacy English menu buttons by re-sending the Uzbek keyboard.

    When the user's chat still shows the old English persistent keyboard
    (left over from a previous bot version), pressing those buttons would
    otherwise be a no-op because the handlers now match Uzbek text. This
    handler catches the legacy text, sends the fresh Uzbek reply keyboard,
    and tells the user to pick from it.
    """
    await message.answer(
        "🔄 Menyu yangilandi — endi o'zbekcha.\n"
        "👇 Quyidagi tugmalardan foydalaning:",
        reply_markup=admin_menu(),
    )


__all__ = ["router"]
