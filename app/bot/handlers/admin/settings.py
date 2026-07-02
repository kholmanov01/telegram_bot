"""Settings handlers — view, edit, backup info.

Covers:

- ``SettingsCallback(action="set", key)`` — start the edit FSM for the key.
- ``SettingsCallback(action="back", key="root")`` — return to the admin menu.
- ``SettingsCallback(action="edit", key)`` — alternative entry-point alias.
- ``_SettingsEditStates.waiting_value`` — captures the new value typed by the
  admin and writes it via :class:`SettingsService.set`.

Editable keys (matching :func:`app.bot.keyboards.admin.settings_inline`):

- ``working_hours_start``, ``working_hours_end``
- ``app_timezone``
- ``default_language``
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from loguru import logger

from app.bot.keyboards.admin import admin_menu, settings_inline
from app.bot.keyboards.callbacks import SettingsCallback
from app.notifications.templates import error_message, settings_menu
from app.services.settings import SettingsService
from app.utils.formatting import escape_html
from app.utils.security import sanitize_text

router = Router(name="admin.settings")


class _SettingsEditStates(StatesGroup):
    """Single-state FSM used to capture a new setting value."""

    waiting_value = State()


_SETTING_LABELS: dict[str, str] = {
    "working_hours_start": "🕘 Ish vaqti boshlanishi (HH:MM)",
    "working_hours_end": "🕚 Ish vaqti tugashi (HH:MM)",
    "app_timezone": "🌍 Vaqt zonasi (IANA, masalan: Asia/Tashkent)",
    "default_language": "🔤 Til kodi (masalan: uz)",
}


@router.callback_query(
    SettingsCallback.filter(F.action == "set"),
    StateFilter(None),
)
async def setting_set(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext,
) -> None:
    """Begin editing a setting — show the current value and ask for a new one."""
    key = callback_data.key
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    try:
        current = await SettingsService().get(key)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Settings get failed for {}: {}", key, exc)
        await message.answer(error_message())
        await callback.answer()
        return

    label = _SETTING_LABELS.get(key, key)
    await state.clear()
    await state.update_data(editing_key=key)
    await state.set_state(_SettingsEditStates.waiting_value)
    await message.answer(
        f"⚙️ <b>Sozlama:</b> {escape_html(label)}\n"
        f"<b>Joriy qiymat:</b> <code>{escape_html(current or '—')}</code>\n\n"
        "Yangi qiymatni kiriting:",
    )
    await callback.answer()


@router.message(
    StateFilter(_SettingsEditStates.waiting_value),
    F.text,
)
async def setting_apply_value(message: Message, state: FSMContext) -> None:
    """Apply the typed value to the stored setting key."""
    raw = sanitize_text(message.text or "", max_length=255)
    if not raw:
        await message.answer("⚠️ Qiymat bo'sh bo'lishi mumkin emas. Qaytadan kiriting.")
        return

    data = await state.get_data()
    key = data.get("editing_key")
    if not key:
        await state.clear()
        await message.answer(error_message(), reply_markup=admin_menu())
        return

    try:
        await SettingsService().set(key, raw)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Settings set failed for {}: {}", key, exc)
        await state.clear()
        await message.answer(error_message(), reply_markup=admin_menu())
        return

    await state.clear()
    await message.answer(
        f"✅ <b>Sozlama yangilandi.</b>\n"
        f"<code>{escape_html(key)}</code> = <code>{escape_html(raw)}</code>",
        reply_markup=admin_menu(),
    )
    logger.info("Setting {} updated by admin", key)


# --------------------------------------------------------------------------- #
# Back / cancel from settings
# --------------------------------------------------------------------------- #
@router.callback_query(
    SettingsCallback.filter(F.action == "back"),
    StateFilter(None),
)
async def setting_back(callback: CallbackQuery) -> None:
    """Return to the admin menu from the settings panel."""
    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            "🏠 <b>Bosh menyu</b>",
            reply_markup=admin_menu(),
        )
    await callback.answer()


# --------------------------------------------------------------------------- #
# Backup info
# --------------------------------------------------------------------------- #
@router.callback_query(
    SettingsCallback.filter(F.action == "edit") & (F.key == "backup"),
    StateFilter(None),
)
async def setting_backup_info(callback: CallbackQuery) -> None:
    """Explain that backups are handled at the infra level (docker volume).

    Per the project conventions, the Postgres data lives in a docker-compose
    volume; a cron / pg_dump job at the host level is responsible for
    backups. Here we simply inform the admin and offer an export of the
    current settings list as a poor-man's snapshot.
    """
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    try:
        all_settings = await SettingsService().get_all()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to load settings list: {}", exc)
        await message.answer(error_message())
        await callback.answer()
        return

    lines: list[str] = [
        "🗄 <b>Zaxira nusxa (backup) haqida</b>",
        "",
        "• Ma'lumotlar bazasi Docker volume orqali saqlanadi.",
        "• To'liq backup docker-compose / pg_dump bilan infra darajasida amalga oshiriladi.",
        "",
        "📋 <b>Joriy sozlamalar ro'yxati:</b>",
    ]
    for s in all_settings:
        lines.append(
            f"• <code>{escape_html(s.key)}</code> = <code>{escape_html(s.value)}</code>"
        )
    if not all_settings:
        lines.append("— (bo'sh)")

    await message.answer("\n".join(lines), reply_markup=admin_menu())
    await callback.answer()


# Silence "unused" warnings — InlineKeyboardMarkup is re-exported for
# downstream packagers.
_ = (settings_menu, settings_inline, InlineKeyboardMarkup)

__all__ = ["router"]
