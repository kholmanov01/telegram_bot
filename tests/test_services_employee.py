"""Tests for EmployeeService.generate_code — code sequence format (mocked repo)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.services.employee import EmployeeService


async def test_generate_code_from_empty(monkeypatch, fake_session) -> None:
    """When no employees exist, the first code is EMP001."""
    fake_repo = MagicMock()
    fake_repo.get_max_code_number = AsyncMock(return_value=0)
    monkeypatch.setattr(
        "app.services.employee.EmployeeRepository",
        lambda session: fake_repo,
    )

    service = EmployeeService.with_session(fake_session)
    code = await service.generate_code()
    assert code == "EMP001"


async def test_generate_code_increments(monkeypatch, fake_session) -> None:
    """The next code is max+1, zero-padded to 3 digits."""
    fake_repo = MagicMock()
    fake_repo.get_max_code_number = AsyncMock(return_value=42)
    monkeypatch.setattr(
        "app.services.employee.EmployeeRepository",
        lambda session: fake_repo,
    )

    service = EmployeeService.with_session(fake_session)
    code = await service.generate_code()
    assert code == "EMP043"


async def test_generate_code_large_number(monkeypatch, fake_session) -> None:
    """Codes beyond 999 keep growing without truncation."""
    fake_repo = MagicMock()
    fake_repo.get_max_code_number = AsyncMock(return_value=999)
    monkeypatch.setattr(
        "app.services.employee.EmployeeRepository",
        lambda session: fake_repo,
    )

    service = EmployeeService.with_session(fake_session)
    code = await service.generate_code()
    assert code == "EMP1000"
