"""Database session middleware.

Opens an :class:`AsyncSession` per update, injects it into ``data["session"]``
and closes it (committing on success / rolling back on error) after the
handler chain has run.

Repositories & services that prefer to receive a session can pick it up from
``data["session"]``; those that prefer to open their own session (the project
default for services) simply ignore it.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database.session import async_session_maker

__all__ = ["DatabaseMiddleware"]


class DatabaseMiddleware(BaseMiddleware):
    """Inject a per-update :class:`AsyncSession` into the handler kwargs.

    The session is committed on success and rolled back on exception. Any
    error raised by the handler is re-raised after the session is closed so
    upstream error handlers still see it.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = async_session_maker()
        data["session"] = session
        try:
            result = await handler(event, data)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
