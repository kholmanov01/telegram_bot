"""Employee profile-related callbacks.

Handles the inline buttons under the profile card rendered by
:func:`app.bot.handlers.employee.menu.cmd_profile`:

- ``MenuCallback(action="my_stats")``       — :func:`cb_my_stats`
- ``MenuCallback(action="notifications")``  — :func:`cb_notifications_settings`

Both render into the same message slot (via ``edit_text``) and attach a
``‹ Back`` inline button to return to the menu.
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.employee.menu import _resolve_employee
from app.bot.keyboards.callbacks import MenuCallback
from app.bot.keyboards.common import back_inline
from app.models.user import User
from app.notifications.templates import error_message, not_authorized
from app.services.statistics import StatisticsService
from app.utils.formatting import divider, stats_card

router = Router(name="employee.profile")


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
# Handlers
# --------------------------------------------------------------------------- #
@router.callback_query(MenuCallback.filter(F.action == "my_stats"))
async def cb_my_stats(
    callback: CallbackQuery,
    callback_data: MenuCallback,  # noqa: ARG001 — needed for filter
    user: User | None = None,
    session: AsyncSession | None = None,  # noqa: ARG001 — injected by mw
) -> None:
    """Render the employee's aggregate statistics card."""
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await callback.answer(not_authorized(), show_alert=True)
            return
        stats = await StatisticsService().employee_stats(employee.id)
        text = stats_card(stats)
        await _safe_edit(callback, text, reply_markup=back_inline())
        await callback.answer()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_my_stats: {}", exc)
        await callback.answer(error_message(), show_alert=True)


@router.callback_query(MenuCallback.filter(F.action == "notifications"))
async def cb_notifications_settings(
    callback: CallbackQuery,
    callback_data: MenuCallback,  # noqa: ARG001 — needed for filter
    user: User | None = None,
    session: AsyncSession | None = None,  # noqa: ARG001 — injected by mw
) -> None:
    """Read-only placeholder for notification preferences.

    The employee receives the following notification types automatically:

    - 📌 new task assigned
    - ⏰ reminder before the deadline
    - ❌ deadline passed

    A future iteration may add per-type opt-in toggles.
    """
    try:
        employee = await _resolve_employee(user, session)
        if employee is None:
            await callback.answer(not_authorized(), show_alert=True)
            return
        text = (
            f"{divider()}\n"
            "🔔 <b>Bildirishnomalar sozlamalari</b>\n"
            "Sizga quyidagi bildirishnomalar yuboriladi:\n"
            "• 📌 Yangi vazifa biriktirilganda\n"
            "• ⏰ Muddat yaqinlashganda (eslatma)\n"
            "• ❌ Muddat o'tganda\n"
            "\n"
            "<i>Boshqa sozlamalar tez orada qo'shiladi.</i>\n"
            f"{divider()}"
        )
        await _safe_edit(callback, text, reply_markup=back_inline())
        await callback.answer()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception("employee.cb_notifications_settings: {}", exc)
        await callback.answer(error_message(), show_alert=True)
