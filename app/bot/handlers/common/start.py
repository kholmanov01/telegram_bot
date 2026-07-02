"""``/start`` command and ``start`` inline callback.

Routes the user to the appropriate surface based on their role and
registration state:

- Super admins   → ``admin_welcome()`` + ``admin_menu()``.
- Registered employees → ``employee_welcome(full_name)`` + ``employee_menu()``.
- Unregistered users → ``welcome_message()`` + ``ask_employee_code()`` and
  the :attr:`RegistrationStates.waiting_employee_code` FSM state is set.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
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
    employee_welcome,
    welcome_message,
)
from app.services.auth import AuthService

router = Router(name="common.start")


# --------------------------------------------------------------------------- #
# /start command
# --------------------------------------------------------------------------- #
@router.message(
    Command("start"),
    StateFilter(None, RegistrationStates.waiting_employee_code),
)
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Handle ``/start`` — bootstrap or re-route the user.

    Matches both the clean state (``None``) and the registration state so
    that a user stuck in the registration flow can always restart with
    ``/start``.
    """
    tg = message.from_user
    if tg is None:
        return

    auth = AuthService()
    try:
        db_user = await auth.get_or_create_user(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            last_name=tg.last_name,
            language_code=tg.language_code,
        )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("get_or_create_user failed for tg_id={}: {}", tg.id, exc)
        await message.answer(
            "⚠️ Texnik nosozlik. Iltimos, keyinroq urinib ko'ring."
        )
        return

    await _route_user(message, state, db_user, auth, tg.id)
    logger.info("/start handled for tg_id={} role={}", tg.id, db_user.role)


# --------------------------------------------------------------------------- #
# "start" inline callback (e.g. from a ‹ Back button on the welcome screen)
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "start", StateFilter(None))
async def cb_start(
    callback: CallbackQuery,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Handle the ``start`` inline button — same routing as ``/start``."""
    tg = callback.from_user
    if tg is None:
        await callback.answer()
        return

    auth = AuthService()
    try:
        db_user = await auth.get_or_create_user(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            last_name=tg.last_name,
            language_code=tg.language_code,
        )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("get_or_create_user failed for tg_id={}: {}", tg.id, exc)
        await callback.message.answer(  # type: ignore[union-attr]
            "⚠️ Texnik nosozlik. Iltimos, keyinroq urinib ko'ring."
        )
        await callback.answer()
        return

    message = callback.message
    if isinstance(message, Message):
        await _route_user(message, state, db_user, auth, tg.id)
    await callback.answer()
    logger.info("'start' callback handled for tg_id={}", tg.id)


# --------------------------------------------------------------------------- #
# Core routing helper
# --------------------------------------------------------------------------- #
async def _route_user(
    message: Message,
    state: FSMContext,
    db_user: User,
    auth: AuthService,
    telegram_id: int,
) -> None:
    """Clear state and route the user to the right surface.

    Args:
        message: Telegram message to answer to.
        state: FSM context for the user's chat.
        db_user: Resolved :class:`User` row (just created or refreshed).
        auth: :class:`AuthService` instance (for ``is_super_admin``).
        telegram_id: The user's Telegram id.
    """
    await state.clear()

    # Super admin — direct to the admin panel.
    if auth.is_super_admin(telegram_id) or db_user.role == UserRole.SUPER_ADMIN:
        await message.answer(admin_welcome(), reply_markup=admin_menu())
        return

    # Already registered employee — show employee menu.
    if db_user.is_registered:
        employee = await get_employee_by_user_id(db_user.id)
        full_name = (
            employee.full_name
            if employee is not None
            else (db_user.first_name or "Foydalanuvchi")
        )
        await message.answer(
            employee_welcome(full_name),
            reply_markup=employee_menu(),
        )
        return

    # Unregistered — start the employee-code registration flow.
    await state.set_state(RegistrationStates.waiting_employee_code)
    await message.answer(welcome_message(), reply_markup=cancel_keyboard())
    await message.answer(ask_employee_code())


# Re-exported for type-checkers / docs.
__all__: list[str] = ["router"]
