"""Shared pytest fixtures.

Tests run without a real database — the service tests use a fake async
session and monkeypatched repositories.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def fake_session() -> Any:
    """Return a mock :class:`AsyncSession` usable by services/repos."""
    session = AsyncMock(name="AsyncSession")
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    # `async with get_session()`-style usage is tested at the service level
    # with `with_session`, so the mock does not need to be a context manager.
    return session


@pytest.fixture
def make_employee_repo():
    """Factory building a mocked :class:`EmployeeRepository`."""
    def _factory(max_code: int = 0) -> MagicMock:
        repo = MagicMock()
        repo.get_max_code_number = AsyncMock(return_value=max_code)
        repo.create = AsyncMock()
        repo.get_by_code = AsyncMock(return_value=None)
        repo.get_active_employees = AsyncMock(return_value=[])
        return repo
    return _factory
