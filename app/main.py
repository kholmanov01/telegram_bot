"""Application entry point.

Boots the Enterprise Telegram Task Management Bot:

1. Configures structured logging (Loguru → info/warning/error.log).
2. Verifies database connectivity (best-effort).
3. Wires middlewares, handlers and the scheduler onto the Dispatcher.
4. Starts long-polling and runs until interrupted.
5. Shuts everything down gracefully on SIGINT/SIGTERM.

Run with::

    python -m app.main
"""

from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import suppress

from loguru import logger

from app.bot.instance import bot, dp
from app.config.logging import setup_logging
from app.config.settings import settings
from app.database.session import engine, init_db
from app.scheduler import register_scheduler, scheduler


async def _on_startup() -> None:
    """Prepare all subsystems before polling starts."""
    logger.info("Starting Enterprise Task Manager Bot | env={}", settings.app_env)

    # Best-effort DB connectivity check. Schema is managed by Alembic.
    try:
        await init_db()
        logger.info("Database connection verified.")
    except Exception as exc:  # pragma: no cover
        logger.error("Database connection failed: {!r}", exc)
        logger.warning("Continuing startup — DB operations will retry per request.")

    # Register the global exception handler, middlewares and routers.
    from app.bot.handlers.common import register_common
    from app.bot.handlers.admin import register_admin
    from app.bot.handlers.employee import register_employee
    from app.bot.middlewares import register_middlewares

    register_middlewares(dp)
    register_common(dp)
    register_employee(dp)
    register_admin(dp)

    # Configure and start the background scheduler (expiry + reminders).
    register_scheduler()
    await scheduler.start()
    logger.info("Scheduler started with {} jobs.", len(scheduler.scheduler.get_jobs()))

    # Announce the bot to Telegram and log its identity.
    me = await bot.get_me()
    logger.info("Bot connected: @{} (id={})", me.username, me.id)


async def _on_shutdown() -> None:
    """Release resources on shutdown."""
    logger.info("Shutting down...")
    with suppress(Exception):
        await scheduler.shutdown()
    with suppress(Exception):
        await dp.stop_polling()
    with suppress(Exception):
        await bot.session.close()
    with suppress(Exception):
        await engine.dispose()
    logger.info("Shutdown complete. Bye!")


async def main() -> None:
    """Run the bot (long-polling OR webhook) until a termination signal."""
    setup_logging()
    await _on_startup()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _request_stop() -> None:
        if not stop_event.is_set():
            logger.info("Stop signal received.")
            stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)

    try:
        if settings.use_webhook:
            await _run_webhook(stop_event)
        else:
            await _run_polling(stop_event)
    finally:
        await _on_shutdown()


async def _run_polling(stop_event: asyncio.Event) -> None:
    """Long-polling mode (default; works behind NAT / no public URL needed)."""
    polling = asyncio.create_task(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    )
    stop_waiter = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait(
        {polling, stop_waiter}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def _run_webhook(stop_event: asyncio.Event) -> None:
    """Webhook mode (for public-HTTPS deployment; required by some free tiers).

    Starts a built-in aiohttp web server that listens for Telegram updates
    on ``webhook_path`` and a health-check on ``healthcheck_path``.
    """
    from aiogram.webhook.aiohttp_server import SimpleAiogramRequestHandler, setup_application
    from aiohttp import web

    if not settings.webhook_url:
        raise RuntimeError("USE_WEBHOOK=true but WEBHOOK_URL is not set")

    app_web = web.Application()
    SimpleAiogramRequestHandler(dispatcher=dp, bot=bot).register(
        app_web, path=settings.webhook_path
    )

    # Minimal health-check endpoint (GET /health → 200 OK).
    async def _health(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    app_web.router.add_get(settings.healthcheck_path, _health)

    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)
    await site.start()
    logger.info(
        "Webhook server listening on {}:{}{}",
        settings.webhook_host,
        settings.webhook_port,
        settings.webhook_path,
    )

    # Register the webhook with Telegram.
    await bot.set_webhook(
        settings.webhook_url,
        drop_pending_updates=True,
    )
    logger.info("Webhook registered with Telegram: {}", settings.webhook_url)

    # Block until stopped.
    await stop_event.wait()

    # Cleanup.
    with suppress(Exception):
        await bot.delete_webhook()
    await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception:  # pragma: no cover
        logger.exception("Fatal error in main loop.")
        sys.exit(1)
