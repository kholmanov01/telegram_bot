"""Employee management handlers — list / create / view / deactivate / activate.

Covers:

- ``EmployeeCallback(action="new")`` — start the employee-creation wizard.
- ``EmployeeCallback(action="view")`` (outside the task wizard) — render the
  employee profile card with their task counts.
- ``EmployeeCallback(action="tasks")`` — show that employee's tasks.
- ``EmployeeCallback(action="deactivate"/"activate")`` — toggle ``is_active``.
- The 4-step creation FSM (full_name → position → department → phone).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from app.bot.keyboards.admin import admin_menu, cancel_keyboard, task_list_inline
from app.bot.keyboards.callbacks import ConfirmCallback, EmployeeCallback, MenuCallback
from app.bot.states.employee import EmployeeCreationStates
from app.models.enums import TaskStatus
from app.models.user import User
from app.notifications.templates import (
    error_message,
    no_tasks,
)
from app.services.employee import EmployeeService
from app.services.task import TaskService
from app.utils.formatting import employee_card, escape_html
from app.utils.security import sanitize_text

router = Router(name="admin.employees")


# --------------------------------------------------------------------------- #
# action="new" — start the creation wizard
# --------------------------------------------------------------------------- #
@router.callback_query(
    EmployeeCallback.filter(F.action == "new"),
    StateFilter(None),
)
async def emp_new(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Begin the employee-creation wizard at the full-name step."""
    await state.clear()
    await state.set_state(EmployeeCreationStates.waiting_full_name)
    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            "👤 Yangi xodim ismi va familiyasini kiriting:",
            reply_markup=cancel_keyboard(),
        )
    await callback.answer()


# --------------------------------------------------------------------------- #
# Creation FSM
# --------------------------------------------------------------------------- #
@router.message(
    StateFilter(EmployeeCreationStates.waiting_full_name),
    F.text,
)
async def create_full_name(message: Message, state: FSMContext) -> None:
    """Capture the full name and advance to the position step."""
    full_name = sanitize_text(message.text or "", max_length=255)
    if not full_name:
        await message.answer("⚠️ Ism bo'sh bo'lishi mumkin emas. Qaytadan kiriting.")
        return

    await state.update_data(full_name=full_name)
    await state.set_state(EmployeeCreationStates.waiting_position)
    await message.answer(
        "💼 Lavozimini kiriting (yoki o'tkazib yuborish uchun «/skip»):"
    )


@router.message(
    StateFilter(EmployeeCreationStates.waiting_position),
    F.text,
)
async def create_position(message: Message, state: FSMContext) -> None:
    """Capture the position (optional) and advance to the department step."""
    raw = sanitize_text(message.text or "", max_length=128)
    position: str | None = None if raw in {"/skip", "—", ""} else raw

    await state.update_data(position=position)
    await state.set_state(EmployeeCreationStates.waiting_department)
    await message.answer(
        "🏢 Bo'limini kiriting (yoki o'tkazib yuborish uchun «/skip»):"
    )


@router.message(
    StateFilter(EmployeeCreationStates.waiting_department),
    F.text,
)
async def create_department(message: Message, state: FSMContext) -> None:
    """Capture the department (optional) and advance to the phone step."""
    raw = sanitize_text(message.text or "", max_length=128)
    department: str | None = None if raw in {"/skip", "—", ""} else raw

    await state.update_data(department=department)
    await state.set_state(EmployeeCreationStates.waiting_phone)
    await message.answer(
        "📞 Telefon raqamini kiriting (yoki o'tkazib yuborish uchun «/skip»):"
    )


@router.message(
    StateFilter(EmployeeCreationStates.waiting_phone),
    F.text,
)
async def create_phone(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Capture the phone (optional) and create the employee row."""
    raw = sanitize_text(message.text or "", max_length=32)
    phone: str | None = None if raw in {"/skip", "—", ""} else raw

    data = await state.get_data()
    created_by = user.id if user is not None else None

    try:
        employee = await EmployeeService().create_employee(
            full_name=data["full_name"],
            position=data.get("position"),
            department=data.get("department"),
            phone=phone,
            created_by=created_by,
        )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to create employee: {}", exc)
        await state.clear()
        await message.answer(error_message(), reply_markup=admin_menu())
        return

    await state.clear()
    await message.answer(
        f"✅ <b>Xodim muvaffaqiyatli yaratildi!</b>\n"
        f"📛 <b>Kod:</b> <code>{escape_html(employee.code)}</code>\n"
        f"👤 <b>Ism:</b> {escape_html(employee.full_name)}",
        reply_markup=admin_menu(),
    )
    logger.info(
        "Admin {} created employee code={}",
        created_by,
        employee.code,
    )


# --------------------------------------------------------------------------- #
# action="view" — employee profile (only fires OUTSIDE the task wizard,
# which has its own EmployeeCallback(action="view") handler guarded by
# StateFilter(waiting_employee)).
# --------------------------------------------------------------------------- #
@router.callback_query(
    EmployeeCallback.filter(F.action == "view"),
    StateFilter(None),
)
async def emp_view(
    callback: CallbackQuery,
    callback_data: EmployeeCallback,
) -> None:
    """Render an employee profile card with task counts + actions."""
    try:
        employee_id = int(callback_data.employee_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri xodim.", show_alert=True)
        return

    employee = await EmployeeService().get_employee(employee_id)
    if employee is None:
        await callback.answer("Xodim topilmadi.", show_alert=True)
        return

    # Count tasks by status for a quick summary.
    try:
        all_tasks = await TaskService().get_employee_tasks(employee_id)
        pending = sum(1 for t in all_tasks if t.status == TaskStatus.PENDING)
        completed = sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED)
        expired = sum(1 for t in all_tasks if t.status == TaskStatus.EXPIRED)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning("Failed to load employee tasks: {}", exc)
        pending = completed = expired = 0

    summary = (
        employee_card(employee)
        + f"\n📊 <b>Vazifalar:</b> ⏳ {pending} · ✅ {completed} · ❌ {expired}"
    )

    toggle_action = "deactivate" if employee.is_active else "activate"
    toggle_label = "🔴 Deaktivatsiya" if employee.is_active else "🟢 Aktivatsiya"
    eid = str(employee_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Vazifalari",
                    callback_data=EmployeeCallback(
                        action="tasks", employee_id=eid
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=toggle_label,
                    callback_data=EmployeeCallback(
                        action=toggle_action, employee_id=eid
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 O'chirish",
                    callback_data=ConfirmCallback(
                        action="yes",
                        payload=f"delete_employee:{eid}",
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="‹ Orqaga",
                    callback_data=MenuCallback(action="back").pack(),
                )
            ],
        ]
    )

    message = callback.message
    if isinstance(message, Message):
        await message.answer(summary, reply_markup=kb)
    await callback.answer()


# --------------------------------------------------------------------------- #
# action="tasks" — list the employee's tasks
# --------------------------------------------------------------------------- #
@router.callback_query(EmployeeCallback.filter(F.action == "tasks"))
async def emp_tasks(
    callback: CallbackQuery,
    callback_data: EmployeeCallback,
) -> None:
    """Show all tasks assigned to an employee."""
    try:
        employee_id = int(callback_data.employee_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri xodim.", show_alert=True)
        return

    try:
        tasks = await TaskService().get_employee_tasks(employee_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to load employee tasks: {}", exc)
        await callback.message.answer(error_message())  # type: ignore[union-attr]
        await callback.answer()
        return

    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    if not tasks:
        await message.answer(no_tasks())
        await callback.answer()
        return

    await message.answer(
        f"📋 <b>Xodim vazifalari ({len(tasks)} ta)</b>",
        reply_markup=task_list_inline(tasks),
    )
    await callback.answer()


# --------------------------------------------------------------------------- #
# action="deactivate" / "activate"
# --------------------------------------------------------------------------- #
@router.callback_query(
    EmployeeCallback.filter(F.action == "deactivate")
)
async def emp_deactivate(
    callback: CallbackQuery,
    callback_data: EmployeeCallback,
) -> None:
    """Mark the employee inactive."""
    try:
        employee_id = int(callback_data.employee_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri xodim.", show_alert=True)
        return

    try:
        await EmployeeService().deactivate_employee(employee_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to deactivate employee: {}", exc)
        await callback.answer("Xatolik.", show_alert=True)
        return

    message = callback.message
    if isinstance(message, Message):
        await message.answer("🔴 Xodim deaktivlashtirildi.")
    await callback.answer("✅ Bajarildi.")


@router.callback_query(EmployeeCallback.filter(F.action == "activate"))
async def emp_activate(
    callback: CallbackQuery,
    callback_data: EmployeeCallback,
) -> None:
    """Re-activate the employee."""
    try:
        employee_id = int(callback_data.employee_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri xodim.", show_alert=True)
        return

    try:
        await EmployeeService().activate_employee(employee_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to activate employee: {}", exc)
        await callback.answer("Xatolik.", show_alert=True)
        return

    message = callback.message
    if isinstance(message, Message):
        await message.answer("🟢 Xodim aktivlashtirildi.")
    await callback.answer("✅ Bajarildi.")


# --------------------------------------------------------------------------- #
# Employee deletion (full removal with confirmation)
# --------------------------------------------------------------------------- #
@router.callback_query(
    ConfirmCallback.filter(
        (F.action == "yes") & F.payload.startswith("delete_employee:")
    ),
)
async def emp_delete_confirm(
    callback: CallbackQuery,
    callback_data: ConfirmCallback,
) -> None:
    """Permanently delete the employee after confirmation.

    The employee card's ``🗑 O'chirish`` button is actually a pre-confirmation
    button carrying ``ConfirmCallback(action="yes", payload="delete_employee:<id>")``.
    We ask for a second confirmation here to avoid accidental deletions.
    """
    payload = callback_data.payload or ""
    parts = payload.split(":", 1)
    if len(parts) != 2:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return
    try:
        employee_id = int(parts[1])
    except ValueError:
        await callback.answer("Noto'g'ri xodim.", show_alert=True)
        return

    # Show a second confirmation — delete is permanent.
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, o'chirish",
                    callback_data=ConfirmCallback(
                        action="no",  # reuse: "no" = confirmed-delete (second step)
                        payload=f"delete_employee_confirm:{employee_id}",
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Yo'q",
                    callback_data=MenuCallback(action="back").pack(),
                ),
            ]
        ]
    )
    await message.answer(
        "⚠ <b>Xodimni butunlay o'chirilsinmi?</b>\n\n"
        "Barcha vazifalar va biriktirilgan fayllar ham o'chiriladi.\n"
        "Bu amalni bekor qilib bo'lmaydi!",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(
    ConfirmCallback.filter(
        (F.action == "no") & F.payload.startswith("delete_employee_confirm:")
    ),
)
async def emp_delete_execute(
    callback: CallbackQuery,
    callback_data: ConfirmCallback,
) -> None:
    """Actually delete the employee (second confirmation received)."""
    payload = callback_data.payload or ""
    parts = payload.split(":", 1)
    if len(parts) != 2:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return
    try:
        employee_id = int(parts[1])
    except ValueError:
        await callback.answer("Noto'g'ri xodim.", show_alert=True)
        return

    try:
        success, msg = await EmployeeService().delete_employee(employee_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to delete employee {}: {}", employee_id, exc)
        await callback.answer("Xatolik.", show_alert=True)
        return

    message = callback.message
    if not success:
        if isinstance(message, Message):
            await message.answer(f"❌ {msg}")
        await callback.answer()
        return

    if isinstance(message, Message):
        await message.answer(
            f"🗑 <b>Xodim o'chirildi.</b>\n{msg}",
            reply_markup=admin_menu(),
        )
    await callback.answer("✅ O'chirildi.")


__all__ = ["router"]
