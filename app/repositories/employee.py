"""Repository for the :class:`Employee` aggregate."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import Employee
from app.repositories.base import BaseRepository

# Matches the numeric suffix of an employee code ``EMP###``.
_EMP_CODE_RE = re.compile(r"^EMP0*(\d+)$", re.IGNORECASE)


class EmployeeRepository(BaseRepository[Employee]):
    """Data-access layer for :class:`Employee` records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a session and the Employee model."""
        super().__init__(session, Employee)

    async def get_by_code(self, code: str) -> Employee | None:
        """Return the employee matching the given code, or ``None``.

        Args:
            code: Human-readable employee code (e.g. ``EMP001``).

        Returns:
            The :class:`Employee` instance or ``None``.
        """
        stmt = select(Employee).where(Employee.code == code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_employees(self) -> list[Employee]:
        """Return all currently active employees ordered by code ascending."""
        stmt = select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.code.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_max_code_number(self) -> int:
        """Return the integer suffix of the highest ``EMP###`` code, or 0 if none.

        Iterates over all existing codes and parses the numeric portion safely.
        Codes that do not match the expected format are ignored.
        """
        stmt = select(Employee.code)
        result = await self.session.execute(stmt)
        codes: list[str] = list(result.scalars().all())

        max_number: int = 0
        for code in codes:
            if not code:
                continue
            match = _EMP_CODE_RE.match(code)
            if match is None:
                continue
            try:
                number = int(match.group(1))
            except (TypeError, ValueError):
                continue
            if number > max_number:
                max_number = number
        return max_number

    async def get_with_user(self, employee_id: int) -> Employee | None:
        """Return the employee by id with its linked :class:`User` eagerly loaded.

        Args:
            employee_id: Primary key of the employee.

        Returns:
            The :class:`Employee` instance with ``user`` populated, or ``None``.
        """
        stmt = (
            select(Employee)
            .options(selectinload(Employee.user))
            .where(Employee.id == employee_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
