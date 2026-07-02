"""Admin handler bundle.

All admin sub-routers are mounted onto a parent router which is guarded by
:class:`SuperAdminFilter` — every message and callback handled by the admin
bundle must originate from a super admin.

Sub-modules:

- :mod:`menu`        — reply-keyboard menu buttons + ``/admin`` command.
- :mod:`task_create` — 8-step task-creation FSM wizard.
- :mod:`employees`   — employee list / create / view / deactivate.
- :mod:`tasks`       — all-tasks view, filters, details, archive/restore,
  search and Excel/PDF export.
- :mod:`statistics`  — period picker, report rendering, Excel export.
- :mod:`settings`    — settings editor FSM + backup info.
- :mod:`callbacks`   — generic ``MenuCallback`` catch-all (back / home ...).
"""

from __future__ import annotations

from aiogram import Router

from app.bot.filters.role import SuperAdminFilter
from app.bot.handlers.admin import (
    callbacks,
    employees,
    menu,
    settings,
    statistics,
    task_create,
    tasks,
)

__all__ = ["register_admin"]


def register_admin(router: Router) -> None:
    """Mount all admin sub-routers behind :class:`SuperAdminFilter`.

    A dedicated ``admin`` router is created internally so the
    :class:`SuperAdminFilter` guard applies ONLY to admin sub-routers —
    not to the parent router (which the caller may also use for common
    handlers that must remain open to every authenticated user).

    Args:
        router: Parent router (typically the dispatcher's root router).
    """
    admin_router = Router(name="admin")
    # Guard the admin router — both messages and callbacks.
    admin_router.message.filter(SuperAdminFilter())
    admin_router.callback_query.filter(SuperAdminFilter())

    # Register sub-routers. The task_create router must come BEFORE the
    # employees router so that the EmployeeCallback(action="view") handler
    # inside task_create (which only fires inside the waiting_employee FSM
    # state) is checked first when the user is mid-wizard.
    admin_router.include_router(menu.router)
    admin_router.include_router(task_create.router)
    admin_router.include_router(employees.router)
    admin_router.include_router(tasks.router)
    admin_router.include_router(statistics.router)
    admin_router.include_router(settings.router)
    admin_router.include_router(callbacks.router)

    router.include_router(admin_router)
