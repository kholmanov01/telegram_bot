"""Update-level logging middleware.

Logs every update at INFO level via Loguru with the acting user, chat and
update type. Registered as an *outer* update middleware on the Dispatcher
(see :func:`app.bot.middlewares.register_middlewares`) so it runs before any
inner / message / callback middleware.

The middleware never blocks the update — it logs in a defensive ``try/except``
and always calls the next handler.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from loguru import logger

__all__ = ["LoggingMiddleware"]


class LoggingMiddleware(BaseMiddleware):
    """Log a one-line summary of every incoming update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            self._log(event, data)
        except Exception:  # pragma: no cover — defensive
            # Logging must never break request handling.
            pass
        return await handler(event, data)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _log(event: TelegramObject, data: dict[str, Any]) -> None:
        tg_user = data.get("event_from_user") or getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)

        user_repr: str
        if tg_user is not None:
            user_repr = (
                f"id={tg_user.id}"
                + (f" @{tg_user.username}" if getattr(tg_user, "username", None) else "")
                + (
                    f" {tg_user.first_name}"
                    if getattr(tg_user, "first_name", None)
                    else ""
                )
            )
        else:
            user_repr = "anonymous"

        chat_repr: str
        if chat is not None:
            chat_repr = f"chat={getattr(chat, 'id', '?')}"
        else:
            chat_repr = "no-chat"

        # Event class name without the module path.
        event_type = type(event).__name__

        # For callback queries include the (truncated) callback data so we
        # can follow the navigation flow in the logs.
        extra = ""
        cb_data = getattr(event, "data", None)
        if cb_data:
            extra = f" data={cb_data[:64]!r}"
        elif getattr(event, "text", None):
            extra = f" text={event.text[:64]!r}"

        logger.info("UPDATE {} | {} | {}{}", event_type, user_repr, chat_repr, extra)
