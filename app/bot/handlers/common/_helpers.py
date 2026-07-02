"""Private helpers shared by the common handlers.

These helpers wrap tiny data-access patterns that don't justify a service
method but are reused across multiple handler modules (e.g. looking up the
employee linked to a user id).
"""

from __future__ import annotations

from app.database.session import get_session
from app.models.employee import Employee
from app.repositories.employee import EmployeeRepository


async def get_employee_by_user_id(user_id: int) -> Employee | None:
    """Return the :class:`Employee` linked to ``user_id``, or ``None``.

    Opens a short-lived session so the helper works regardless of the
    request's middleware-injected session state.

    Args:
        user_id: Primary key of the :class:`User`.

    Returns:
        The linked :class:`Employee` or ``None``.
    """
    async with get_session() as session:
        repo = EmployeeRepository(session)
        return await repo.find_one(user_id=user_id)


__all__ = ["get_employee_by_user_id"]
