"""Employee self-registration flow.

Single FSM step: the user types their employee code (``EMP001``). The code
is validated locally, then :meth:`AuthService.register_employee` links the
employee to the user (or returns a localised failure reason).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from app.bot.keyboards.common import cancel_keyboard
from app.bot.keyboards.employee import employee_menu
from app.bot.states.registration import RegistrationStates
from app.models.user import User
from app.notifications.templates import (
    ask_employee_code,
    invalid_input,
    registration_failed,
    registration_success,
)
from app.services.auth import AuthService
from app.services.employee import EmployeeService
from app.utils.security import sanitize_text, validate_employee_code

router = Router(name="common.registration")


@router.message(
    StateFilter(RegistrationStates.waiting_employee_code),
    F.text,
)
async def process_employee_code(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Validate and apply the employee code entered by the user."""
    if message.text is None:
        return

    code = sanitize_text(message.text)

    # 1. Local format check — no DB round-trip.
    if not validate_employee_code(code):
        await message.answer(invalid_input("Employee ID"))
        await message.answer(ask_employee_code())
        return

    # 2. Resolve the acting user — fall back to a DB lookup if the
    #    middleware did not inject one.
    telegram_id = message.from_user.id if message.from_user else 0
    user_id: int | None = user.id if user is not None else None
    if user_id is None:
        fetched = await AuthService().get_user_by_telegram_id(telegram_id)
        if fetched is None:
            logger.warning(
                "Registration attempt from unknown tg_id={}", telegram_id
            )
            await message.answer(registration_failed("Foydalanuvchi topilmadi."))
            return
        user_id = fetched.id

    # 3. Ask the auth service to link the employee code.
    try:
        success, reason = await AuthService().register_employee(user_id, code)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("register_employee failed: {}", exc)
        await message.answer(
            registration_failed("Texnik nosozlik. Keyinroq urinib ko'ring.")
        )
        return

    if not success:
        await message.answer(registration_failed(reason))
        await message.answer(ask_employee_code())
        return

    # 4. Success — fetch the employee for a richer confirmation card.
    employee = await EmployeeService().get_employee_by_code(
        code.strip().upper()
    )
    if employee is None:
        # The link succeeded but we couldn't reload — fall back to a
        # minimal confirmation using the reason string.
        await state.clear()
        await message.answer(reason, reply_markup=employee_menu())
        return

    full_name = employee.full_name
    await state.clear()
    await message.answer(
        registration_success(full_name, employee.code),
        reply_markup=employee_menu(),
    )

    logger.info(
        "Employee registered: user_id={} code={}", user_id, employee.code
    )


__all__ = ["router"]
