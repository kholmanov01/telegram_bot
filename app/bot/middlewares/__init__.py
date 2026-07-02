"""Bot middlewares package.

Wires up the four middlewares on the Dispatcher:

- :class:`LoggingMiddleware`     — outer update middleware (runs first).
- :class:`DatabaseMiddleware`    — message + callback_query inner middleware.
- :class:`AuthMiddleware`        — message + callback_query inner middleware.
- :class:`ThrottlingMiddleware`  — message + callback_query inner middleware.

Call :func:`register_middlewares` from the bot entry point (after handlers
have been registered) to install them.
"""

from __future__ import annotations

from aiogram import Dispatcher

from app.bot.middlewares.auth import AuthMiddleware
from app.bot.middlewares.database import DatabaseMiddleware
from app.bot.middlewares.logging import LoggingMiddleware
from app.bot.middlewares.throttling import ThrottlingMiddleware

__all__ = [
    "LoggingMiddleware",
    "DatabaseMiddleware",
    "AuthMiddleware",
    "ThrottlingMiddleware",
    "register_middlewares",
]


def register_middlewares(dp: Dispatcher) -> None:
    """Wire all middlewares onto the given :class:`Dispatcher`.

    Wiring order (per update type):
        1. database   — opens the session, injects ``data["session"]``
        2. auth       — resolves the user (needs the session)
        3. throttling — dedup clicks (last so it can short-circuit cleanly)

    ``LoggingMiddleware`` is attached as an *outer* update middleware so it
    observes every update, including ones that no inner middleware will run
    on.
    """
    dp.update.outer_middleware(LoggingMiddleware())

    db = DatabaseMiddleware()
    auth = AuthMiddleware()
    throttle = ThrottlingMiddleware()

    for event_type in (dp.message, dp.callback_query):
        event_type.outer_middleware(db)
        event_type.outer_middleware(auth)
        event_type.outer_middleware(throttle)
