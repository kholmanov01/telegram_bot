"""Common handlers — shared by every authenticated user.

This package wires together the entry-point handlers:

- :mod:`start`        — ``/start`` command and ``start`` inline callback.
- :mod:`registration` — employee-code registration FSM step.
- :mod:`commands`     — ``/help``, ``/cancel``, ``/id`` and the ``❌ Cancel``
  reply-keyboard button.
- :mod:`attachments`  — view / add task attachments (admin + employee).
- :mod:`errors`       — global exception handler attached to the dispatcher.

Use :func:`register_common` to mount the whole bundle onto a parent router.
"""

from __future__ import annotations

from aiogram import Router

from app.bot.handlers.common import (
    attachments,
    commands,
    errors,
    registration,
    start,
)

__all__ = ["register_common"]


def register_common(router: Router) -> None:
    """Include every common sub-router into ``router``.

    Args:
        router: Parent router (typically the dispatcher's root router).
    """
    router.include_router(start.router)
    router.include_router(registration.router)
    router.include_router(commands.router)
    router.include_router(attachments.router)
    # The errors router must be registered last so that the exception
    # observer is attached after the message/callback observers.
    router.include_router(errors.router)
