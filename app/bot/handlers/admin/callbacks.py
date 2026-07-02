"""Admin catch-all callback handlers.

This module handles generic ``MenuCallback`` actions that aren't owned by
any specific feature module (``back``, ``home`` …) plus any cleanup needed
when the admin dismisses an inline message.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.admin import admin_menu
from app.bot.keyboards.callbacks import MenuCallback

router = Router(name="admin.callbacks")


@router.callback_query(
    MenuCallback.filter(F.action == "back"),
    StateFilter(None),
)
async def menu_back(callback: CallbackQuery) -> None:
    """Generic ``‹ Back`` — return the admin to the main menu."""
    message = callback.message
    if isinstance(message, Message):
        try:
            await message.delete()
        except Exception:  # noqa: BLE001 — defensive
            pass
        await message.answer(
            "🏠 <b>Bosh menyu</b>",
            reply_markup=admin_menu(),
        )
    await callback.answer()


@router.callback_query(
    MenuCallback.filter(F.action == "home"),
    StateFilter(None),
)
async def menu_home(callback: CallbackQuery) -> None:
    """Generic ``home`` — same as ``back`` but without deleting the source."""
    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            "🏠 <b>Bosh menyu</b>",
            reply_markup=admin_menu(),
        )
    await callback.answer()


__all__ = ["router"]
