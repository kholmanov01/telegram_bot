"""Employee management service.

Wraps :class:`EmployeeRepository` with business logic: code generation,
creation with audit logging, lookups, updates and deactivation.

Employee codes follow the format ``EMP###`` where ``###`` is a zero-padded
sequence derived from ``max(existing_code_numbers) + 1``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.models.employee import Employee
from app.models.enums import AuditAction
from app.repositories.audit_log import AuditLogRepository
from app.repositories.employee import EmployeeRepository
from app.utils.dates import now_utc


class EmployeeService:
    """Create, query and update :class:`Employee` records."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "EmployeeService":
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
    async def generate_code(self) -> str:
        """Return the next available employee code (``EMP###``)."""
        async with self._session_scope() as session:
            repo = EmployeeRepository(session)
            max_number = await repo.get_max_code_number()
            next_number = max_number + 1
            return f"EMP{next_number:03d}"

    async def create_employee(
        self,
        full_name: str,
        position: str | None = None,
        department: str | None = None,
        phone: str | None = None,
        created_by: int | None = None,
    ) -> Employee:
        """Create a new employee with an auto-generated code.

        Args:
            full_name: Employee full name.
            position: Optional job title.
            department: Optional department name.
            phone: Optional phone number (stored as-is).
            created_by: User id of the admin creating the employee.

        Returns:
            The newly created :class:`Employee` instance.
        """
        async with self._session_scope() as session:
            emp_repo = EmployeeRepository(session)
            audit_repo = AuditLogRepository(session)

            code = f"EMP{(await emp_repo.get_max_code_number()) + 1:03d}"
            employee = await emp_repo.create(
                {
                    "code": code,
                    "full_name": full_name,
                    "position": position,
                    "department": department,
                    "phone": phone,
                    "is_active": True,
                    "created_by": created_by,
                }
            )

            await audit_repo.create(
                {
                    "action": AuditAction.EMPLOYEE_CREATED,
                    "actor_id": created_by,
                    "target_type": "employee",
                    "target_id": employee.id,
                    "summary": (
                        f"Employee {employee.full_name} ({employee.code}) "
                        "created"
                    ),
                    "detail": {
                        "code": employee.code,
                        "position": position,
                        "department": department,
                    },
                    "occurred_at": now_utc(),
                }
            )

            logger.info(
                "Created employee code={} name={!r} by={}",
                employee.code,
                employee.full_name,
                created_by,
            )
            return employee

    async def get_employee(self, employee_id: int) -> Employee | None:
        """Return the employee by id, or ``None``."""
        async with self._session_scope() as session:
            repo = EmployeeRepository(session)
            return await repo.get_by_id(employee_id)

    async def get_employee_by_code(self, code: str) -> Employee | None:
        """Return the employee by code, or ``None``."""
        async with self._session_scope() as session:
            repo = EmployeeRepository(session)
            return await repo.get_by_code(code)

    async def get_active_employees(self) -> list[Employee]:
        """Return all active employees ordered by code ascending."""
        async with self._session_scope() as session:
            repo = EmployeeRepository(session)
            return await repo.get_active_employees()

    async def update_employee(
        self, employee_id: int, **fields: Any
    ) -> Employee | None:
        """Update one or more columns of an employee.

        Args:
            employee_id: Primary key of the employee.
            **fields: Column names mapped to their new values.

        Returns:
            The updated :class:`Employee`, or ``None`` if not found.
        """
        if not fields:
            # Nothing to update — just return the current row.
            return await self.get_employee(employee_id)

        async with self._session_scope() as session:
            repo = EmployeeRepository(session)
            updated = await repo.update(employee_id, fields)
            if updated is not None:
                logger.info(
                    "Updated employee id={} fields={}",
                    employee_id,
                    list(fields.keys()),
                )
            return updated

    async def deactivate_employee(self, employee_id: int) -> None:
        """Mark an employee as inactive (soft delete)."""
        async with self._session_scope() as session:
            repo = EmployeeRepository(session)
            await repo.update(employee_id, {"is_active": False})
            logger.info("Deactivated employee id={}", employee_id)

    async def activate_employee(self, employee_id: int) -> None:
        """Re-activate a previously deactivated employee."""
        async with self._session_scope() as session:
            repo = EmployeeRepository(session)
            await repo.update(employee_id, {"is_active": True})
            logger.info("Activated employee id={}", employee_id)

    async def delete_employee(self, employee_id: int) -> tuple[bool, str]:
        """Permanently delete an employee and unlink their user account.

        Returns ``(success, message)``. The employee's linked user (if any) is
        kept but unlinked (``user_id`` set to NULL on the employee before
        delete is unnecessary because the FK is ON DELETE SET NULL, but we
        also clear the user's registration so they cannot re-enter).
        """
        async with self._session_scope() as session:
            repo = EmployeeRepository(session)
            employee = await repo.get_by_id(employee_id)
            if employee is None:
                return False, "Xodim topilmadi."

            # Unlink the user account if linked so the freed user can't
            # keep accessing the employee menu. We also mark them
            # unregistered.
            if employee.user_id is not None:
                from app.repositories.user import UserRepository
                user_repo = UserRepository(session)
                linked_user = await user_repo.get_by_id(employee.user_id)
                if linked_user is not None:
                    await user_repo.update(
                        linked_user.id,
                        {"is_registered": False, "registration_date": None},
                    )

            deleted = await repo.delete(employee_id)
            if not deleted:
                return False, "Xodimni o'chirib bo'lmadi."
            logger.info("Deleted employee id={} code={}", employee_id, employee.code)
            return True, f"Xodim {employee.full_name} ({employee.code}) o'chirildi."
