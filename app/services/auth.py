"""Authentication & registration service.

Handles:

* First-touch user creation (``/start``) — a ``User`` row is created with
  role ``EMPLOYEE`` and ``is_registered=False``. Telegram IDs in the
  ``SUPER_ADMIN_IDS`` env allow-list are promoted to ``SUPER_ADMIN`` and
  marked registered immediately.
* Employee code registration — links an :class:`Employee` row to the
  current user, flips ``is_registered=True`` and records an audit entry.

The ``is_super_admin`` helper is synchronous because it only reads the
in-memory settings singleton.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.session import get_session
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.user import UserRepository
from app.utils.dates import now_utc
from app.utils.security import validate_employee_code


class AuthService:
    """User onboarding, role resolution and employee-code registration."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "AuthService":
        """Return an instance bound to ``session`` for in-transaction use."""
        instance = cls()
        instance._session = session
        return instance

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[AsyncSession]:
        """Yield a usable session (injected or freshly opened)."""
        if self._session is not None:
            yield self._session
        else:
            async with get_session() as session:
                yield session

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def is_super_admin(self, telegram_id: int) -> bool:
        """Return ``True`` if ``telegram_id`` is in the env super-admin list.

        This is a **synchronous** check against the settings singleton —
        no DB access is performed. The result is used to bootstrap the
        first super-admin without requiring an existing DB row.
        """
        return telegram_id in settings.super_admin_id_list

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
    ) -> User:
        """Return the user for ``telegram_id``, creating it if absent.

        * For brand-new users a row is inserted with role ``EMPLOYEE`` and
          ``is_registered=False``.
        * If the telegram id is in the env super-admin allow-list the role
          is set to ``SUPER_ADMIN`` and ``is_registered=True``.
        * For existing users the Telegram profile fields (username,
          first/last name, language code) are refreshed and the super-admin
          promotion is re-applied if applicable.
        * ``last_activity`` is always bumped via :func:`touch_activity`.
        """
        async with self._session_scope() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            is_super_admin = self.is_super_admin(telegram_id)

            if user is None:
                data = {
                    "telegram_id": telegram_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "language_code": language_code,
                    "role": (
                        UserRole.SUPER_ADMIN
                        if is_super_admin
                        else UserRole.EMPLOYEE
                    ),
                    "is_registered": is_super_admin,
                    "registration_date": (
                        now_utc() if is_super_admin else None
                    ),
                    "last_activity": now_utc(),
                }
                user = await user_repo.create(data)
                logger.info(
                    "Created user telegram_id={} role={} registered={}",
                    telegram_id,
                    user.role,
                    user.is_registered,
                )
            else:
                # Refresh Telegram-provided profile fields on every contact.
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.language_code = language_code
                # Promote to super-admin if the env list now includes them.
                if is_super_admin and user.role != UserRole.SUPER_ADMIN:
                    user.role = UserRole.SUPER_ADMIN
                    user.is_registered = True
                    if user.registration_date is None:
                        user.registration_date = now_utc()
                await user_repo.save(user)
                logger.info(
                    "User touched telegram_id={} role={}",
                    telegram_id,
                    user.role,
                )

            # Always bump last_activity.
            await user_repo.touch_activity(user.id)
            return user

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> User | None:
        """Return the user with the given Telegram id, or ``None``."""
        async with self._session_scope() as session:
            user_repo = UserRepository(session)
            return await user_repo.get_by_telegram_id(telegram_id)

    async def register_employee(
        self, user_id: int, employee_code: str
    ) -> tuple[bool, str]:
        """Link an employee code to the given user.

        Args:
            user_id: Primary key of the currently-authenticated user.
            employee_code: Code entered by the user (e.g. ``EMP001``).

        Returns:
            A ``(success, message)`` tuple. On success the message
            includes the employee's full name. On failure the message is
            a short, already-localised Uzbek reason.
        """
        # 1. Validate format first — no DB round-trip needed.
        if not validate_employee_code(employee_code):
            return (
                False,
                "Noto'g'ri kod formati. Misol: <code>EMP001</code>",
            )

        # Normalise to canonical upper-case form before lookup.
        code = employee_code.strip().upper()

        async with self._session_scope() as session:
            user_repo = UserRepository(session)
            emp_repo = EmployeeRepository(session)
            audit_repo = AuditLogRepository(session)

            employee = await emp_repo.get_by_code(code)
            if employee is None:
                return (False, "Bunday kod topilmadi")

            # Already linked to a different user.
            if (
                employee.user_id is not None
                and employee.user_id != user_id
            ):
                return (False, "Bu kod allaqachon ishlatilgan")

            # If this employee is already linked to THIS user, the call is
            # idempotent — report success without changing anything.
            already_linked = employee.user_id == user_id

            if not already_linked:
                employee.user_id = user_id
                employee.registered_at = now_utc()
                await emp_repo.save(employee)

            user = await user_repo.get_by_id(user_id)
            # Even if the user was already registered (e.g. they re-ran
            # /start and entered the same code), keep the flags in sync.
            if user is not None:
                user.is_registered = True
                if user.role != UserRole.SUPER_ADMIN:
                    user.role = UserRole.EMPLOYEE
                if user.registration_date is None:
                    user.registration_date = now_utc()
                await user_repo.save(user)

            await audit_repo.create(
                {
                    "action": AuditAction.EMPLOYEE_REGISTERED,
                    "actor_id": user_id,
                    "actor_telegram_id": (
                        user.telegram_id if user is not None else None
                    ),
                    "target_type": "employee",
                    "target_id": employee.id,
                    "summary": (
                        f"Employee {employee.full_name} "
                        f"({employee.code}) registered"
                    ),
                    "detail": {
                        "employee_code": employee.code,
                        "already_linked": already_linked,
                    },
                    "occurred_at": now_utc(),
                }
            )

            logger.info(
                "Registered employee code={} user_id={}",
                employee.code,
                user_id,
            )
            return (
                True,
                f"Tabriklaymiz, {employee.full_name}! "
                "Siz muvaffaqiyatli ro'yxatdan o'tdingiz.",
            )
