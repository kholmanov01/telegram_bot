"""Redis-based throttling middleware.

Prevents the most common form of abuse in Telegram bots — duplicate button
clicks. Each (``user_id``, ``callback_data``) pair is locked in Redis for a
short TTL (default 0.5s). While locked, subsequent identical callbacks from
the same user are answered with a "⏳ Iltimos kuting..." message and the
handler is skipped.

For plain text messages the lock key uses ``user_id:message_text`` so that
rapid double-send of the same command is also deduplicated.

Design choices:
- Fail-open: if Redis is unreachable, the request is allowed through and a
  warning is logged. We never block legitimate traffic because of an
  infrastructure hiccup.
- The Redis client is created lazily on first use and re-used across updates
  (single shared connection).
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger
from redis.asyncio import Redis

from app.config.settings import settings

__all__ = ["ThrottlingMiddleware"]


class ThrottlingMiddleware(BaseMiddleware):
    """Rate-limit duplicate callbacks / messages via Redis."""

    #: Lock TTL in seconds.
    LOCK_TTL: float = 0.5

    def __init__(self, lock_ttl: float | None = None) -> None:
        """Optionally override the lock TTL (seconds)."""
        super().__init__()
        if lock_ttl is not None:
            self.LOCK_TTL = lock_ttl
        self._redis: Redis | None = None  # lazy singleton

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        key = self._build_key(event, data)
        if key is None:
            # Nothing to throttle on (no user / no payload).
            return await handler(event, data)

        redis = await self._get_redis()
        if redis is None:
            # Redis unavailable → fail-open.
            return await handler(event, data)

        try:
            acquired = await redis.set(key, "1", ex=int(self.LOCK_TTL) or 1, nx=True)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("ThrottlingMiddleware: Redis error — fail-open: {!r}", exc)
            return await handler(event, data)

        if not acquired:
            # Duplicate within the TTL window — answer & block.
            await self._answer_blocked(event)
            return None

        try:
            return await handler(event, data)
        finally:
            # Do NOT release the lock — the TTL window is the dedup window.
            pass

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_key(event: TelegramObject, data: dict[str, Any]) -> str | None:
        """Build a Redis key uniquely identifying the duplicated action."""
        tg_user = data.get("event_from_user") or getattr(event, "from_user", None)
        if tg_user is None:
            return None
        if isinstance(event, CallbackQuery):
            payload = event.data or ""
        elif isinstance(event, Message):
            payload = (event.text or "")[:64]
        else:
            payload = ""
        if not payload:
            return None
        return f"throttle:{tg_user.id}:{payload}"

    async def _get_redis(self) -> Redis | None:
        """Return the lazily-initialised Redis client (or ``None`` on failure)."""
        if self._redis is not None:
            return self._redis
        try:
            self._redis = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            await self._redis.ping()
            return self._redis
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "ThrottlingMiddleware: cannot connect to Redis — fail-open: {!r}",
                exc,
            )
            self._redis = None
            return None

    @staticmethod
    async def _answer_blocked(event: TelegramObject) -> None:
        """Politely tell the user the action is being rate-limited."""
        if isinstance(event, CallbackQuery):
            try:
                await event.answer("⏳ Iltimos kuting...", show_alert=False)
            except Exception:  # pragma: no cover — defensive
                pass
        elif isinstance(event, Message):
            # Silent for plain messages — answering every throttled message
            # would be noisier than the duplicate itself.
            pass
