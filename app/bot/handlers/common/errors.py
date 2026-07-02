"""Global exception observer.

Catches unhandled exceptions raised anywhere in the dispatcher, logs them
at ``ERROR`` level via loguru, and attempts a best-effort user notification
(wrapped in its own ``try/except`` so a Telegram failure cannot crash the
observer).
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import ErrorEvent, Message
from loguru import logger

from app.notifications.templates import error_message

router = Router(name="common.errors")


@router.errors()
async def on_unhandled_error(event: ErrorEvent) -> bool:
    """Log the exception and attempt a best-effort user notification.

    Args:
        event: The :class:`aiogram.types.ErrorEvent` wrapping the exception.

    Returns:
        ``True`` to mark the exception as handled.
    """
    exc = event.exception
    update = event.update

    # Log the full exception with traceback.
    logger.error(
        "Unhandled exception in update {!r}: {!r}",
        update.update_id if update else None,
        exc,
    )

    # Best-effort user notification — never raises.
    try:
        if update is not None:
            if update.callback_query is not None:
                try:
                    await update.callback_query.answer(
                        "⚠️ Xatolik yuz berdi.",
                        show_alert=True,
                    )
                except Exception:  # noqa: BLE001 — defensive
                    pass
            elif update.message is not None:
                message: Message = update.message
                try:
                    await message.answer(error_message())
                except Exception:  # noqa: BLE001 — defensive
                    pass
    except Exception as exc2:  # noqa: BLE001 — defensive
        logger.debug("Error observer: notification attempt failed: {!r}", exc2)

    return True


__all__ = ["router"]
