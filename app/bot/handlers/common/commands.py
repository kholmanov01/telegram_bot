"""Global commands and the ``❌ Cancel`` reply-keyboard button.

- ``/help``   — short help text.
- ``/cancel`` — clear FSM state and return to the role-appropriate menu.
- ``/id``     — echo the user's Telegram id (useful for SUPER_ADMIN_IDS).
- ``❌ Cancel`` reply-keyboard button — same behaviour as ``/cancel``.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from app.bot.handlers.common._helpers import get_employee_by_user_id
from app.bot.keyboards.admin import admin_menu
from app.bot.keyboards.common import cancel_keyboard
from app.bot.keyboards.employee import employee_menu
from app.bot.states.registration import RegistrationStates
from app.models.enums import UserRole
from app.models.user import User
from app.notifications.templates import (
    admin_welcome,
    ask_employee_code,
    cancelled,
    employee_welcome,
    welcome_message,
)

router = Router(name="common.commands")

_HELP_TEXT = (
    "ℹ️ <b>Yordam</b>\n"
    "\n"
    "• /start — botni qayta ishga tushirish\n"
    "• /help — shu yordam matni\n"
    "• /cancel — joriy amalni bekor qilish\n"
    "• /id — sizning Telegram ID'ingizni ko'rsatadi\n"
)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Send a short help card."""
    await message.answer(_HELP_TEXT)


@router.message(Command("cancel"))
@router.message(F.text == "❌ Bekor qilish")
async def cmd_cancel(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Clear any active FSM state and route the user back to their menu."""
    await state.clear()
    await message.answer(cancelled())

    # Super admin → admin panel.
    telegram_id = message.from_user.id if message.from_user else 0
    if user is not None and user.role == UserRole.SUPER_ADMIN:
        await message.answer(admin_welcome(), reply_markup=admin_menu())
        return

    # Registered employee → employee menu.
    if user is not None and user.is_registered:
        employee = await get_employee_by_user_id(user.id)
        full_name = (
            employee.full_name
            if employee is not None
            else (user.first_name or "Foydalanuvchi")
        )
        await message.answer(
            employee_welcome(full_name),
            reply_markup=employee_menu(),
        )
        return

    # Unregistered — restart the registration flow.
    await state.set_state(RegistrationStates.waiting_employee_code)
    await message.answer(welcome_message(), reply_markup=cancel_keyboard())
    await message.answer(ask_employee_code())


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    """Echo the user's Telegram id — handy for configuring SUPER_ADMIN_IDS."""
    tg_id = message.from_user.id if message.from_user else 0
    logger.debug("/id from tg_id={}", tg_id)
    await message.answer(
        f"Sizning Telegram ID: <code>{tg_id}</code>"
    )


__all__ = ["router"]
