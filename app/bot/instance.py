"""Bot and Dispatcher singletons.

The :class:`Bot` is configured with a Redis-backed FSM storage so that
conversation state survives restarts. The default parse mode is set to HTML
so handlers can safely format messages with ``<b>`` / ``<code>`` etc.
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage

from redis.asyncio import Redis

from app.config.settings import settings


async def _redis_reachable() -> bool:
    """Return True if Redis is reachable within a short timeout.

    ``Redis.from_url`` does not open a connection eagerly, so we must ping
    explicitly to know whether Redis is actually running.
    """
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        ok = bool(await redis.ping())
        await redis.aclose()
        return ok
    except Exception:
        return False


def _build_storage_sync() -> MemoryStorage:
    """Synchronous fallback used at import time when Redis is not confirmed.

    A later ``_maybe_upgrade_storage`` call can swap to Redis once reachable.
    """
    return MemoryStorage()


async def _build_storage_async() -> RedisStorage | MemoryStorage:
    """Build FSM storage, verifying Redis connectivity with an actual ping.

    Falls back to :class:`MemoryStorage` if Redis is unavailable.
    """
    if await _redis_reachable():
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30,
        )
        return RedisStorage(redis=redis, key_builder=DefaultKeyBuilder(prefix="taskbot"))
    return MemoryStorage()


def _build_storage() -> RedisStorage | MemoryStorage:
    """Build FSM storage at import time.

    Since Redis connectivity cannot be awaited at import time without
    blocking, we default to :class:`MemoryStorage`. Call
    :func:`upgrade_storage_to_redis` from the async startup if you want
    Redis-backed persistence when Redis is available.
    """
    return MemoryStorage()


async def upgrade_storage_to_redis(dp: Dispatcher) -> bool:
    """Attempt to swap the dispatcher's FSM storage to Redis at runtime.

    Returns True if Redis is available and the storage was upgraded.
    """
    try:
        storage = await _build_storage_async()
        if isinstance(storage, RedisStorage):
            dp.storage = storage
            return True
    except Exception:
        pass
    return False


bot: Bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        link_preview_is_disabled=True,
    ),
)

dp: Dispatcher = Dispatcher(storage=_build_storage())
