"""Authorization filters used by handlers.

- :class:`SuperAdminFilter` — passes when the acting Telegram user is in the
  ``SUPER_ADMIN_IDS`` env list (a two-tier check is supported: env list first,
  then optionally the :class:`User` instance injected by the auth middleware).
- :class:`RoleFilter` — passes when the injected ``data["user"]`` has one of
  the accepted roles. The auth middleware always sets ``data["user"]`` (it
  may be a lightweight anonymous stub, see :mod:`app.bot.middlewares.auth`).

Both filters are async and accept either a :class:`Message` or a
:class:`CallbackQuery` (the first positional argument) plus the handler
``data`` dict.
"""

from __future__ import annotations

from typing import Any, Iterable, Union

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from app.config.settings import settings
from app.models.enums import UserRole

__all__ = ["SuperAdminFilter", "RoleFilter"]

# Type alias for the supported event types.
Event = Union[Message, CallbackQuery]


class SuperAdminFilter(Filter):
    """Pass only when the acting user is a super admin.

    Two-tier check:
    1. The Telegram user id is in ``settings.super_admin_id_list`` (env).
    2. Otherwise, if the auth middleware has injected a ``User`` instance in
       ``data["user"]`` whose ``role`` is :attr:`UserRole.SUPER_ADMIN`, pass.
    """

    async def __call__(self, event: Event, **data: Any) -> bool:
        tg_user = getattr(event, "from_user", None)
        if tg_user is None:
            return False

        # Tier 1: env-based allow-list (cheap, no DB hit).
        if tg_user.id in settings.super_admin_id_list:
            return True

        # Tier 2: trust the user object injected by AuthMiddleware.
        user = data.get("user")
        if user is not None:
            role = getattr(user, "role", None)
            if role == UserRole.SUPER_ADMIN:
                return True
        return False


class RoleFilter(Filter):
    """Pass only when the injected user has one of the accepted roles.

    Args:
        roles: One :class:`UserRole` or an iterable of accepted roles.

    The auth middleware is responsible for setting ``data["user"]`` (a
    :class:`app.models.user.User`). When the user is anonymous (not yet
    registered) the filter returns ``False`` — handlers behind this filter
    should be reachable only by authenticated users.
    """

    def __init__(self, roles: UserRole | Iterable[UserRole]) -> None:
        if isinstance(roles, UserRole):
            self._roles: frozenset[UserRole] = frozenset({roles})
        else:
            self._roles = frozenset(roles)

    async def __call__(self, event: Event, **data: Any) -> bool:
        user = data.get("user")
        if user is None:
            return False
        # Must be fully registered to access role-gated handlers.
        # An unregistered user may have role=EMPLOYEE (default) but should
        # not yet reach employee menus.
        if not getattr(user, "is_registered", False):
            return False
        role = getattr(user, "role", None)
        if not isinstance(role, UserRole):
            # Stored enum may have been deserialised as a plain string.
            try:
                role = UserRole(role)
            except (ValueError, TypeError):
                return False
        return role in self._roles
