"""Employee handlers package.

Wires all employee sub-routers under a single :func:`register_employee`
entry point. The role-based guard is applied here (not in the sub-routers)
so every handler in this package only responds to users whose role is
:attr:`UserRole.EMPLOYEE`.

Sub-routers:

- :mod:`app.bot.handlers.employee.menu`      — reply-menu (My Tasks /
  Completed / Today / Notifications / Profile).
- :mod:`app.bot.handlers.employee.tasks`     — task view / complete /
  details callbacks (:class:`TaskCallback`).
- :mod:`app.bot.handlers.employee.profile`   — profile callbacks
  (My Stats, Notifications settings).
- :mod:`app.bot.handlers.employee.callbacks` — pagination + menu ``back``
  callbacks (:class:`PaginationCallback`, :class:`MenuCallback`).
"""

from __future__ import annotations

from aiogram import Router

from app.bot.filters.role import RoleFilter
from app.bot.handlers.employee.callbacks import router as callbacks_router
from app.bot.handlers.employee.menu import router as menu_router
from app.bot.handlers.employee.profile import router as profile_router
from app.bot.handlers.employee.tasks import router as tasks_router
from app.models.enums import UserRole

__all__ = ["register_employee"]


def register_employee(parent: Router) -> None:
    """Attach all employee sub-routers to ``parent`` with a role guard.

    A :class:`RoleFilter(UserRole.EMPLOYEE)` is applied to both the
    ``message`` and ``callback_query`` channels of every sub-router so
    anonymous users and super admins can never reach these handlers.
    """
    sub_routers = (menu_router, tasks_router, profile_router, callbacks_router)
    for router in sub_routers:
        router.message.filter(RoleFilter(UserRole.EMPLOYEE))
        router.callback_query.filter(RoleFilter(UserRole.EMPLOYEE))
        parent.include_router(router)
