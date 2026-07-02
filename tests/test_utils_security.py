"""Tests for app.utils.security."""

from __future__ import annotations

import pytest

from app.utils import security


@pytest.mark.parametrize("code", ["EMP001", "EMP123", "EMP9999", "emp001"])
def test_validate_employee_code_valid(code: str) -> None:
    assert security.validate_employee_code(code) is True


@pytest.mark.parametrize("code", ["EMP1", "EMP", "XYZ123", "EM001", "", "EMP00A"])
def test_validate_employee_code_invalid(code: str) -> None:
    assert security.validate_employee_code(code) is False


def test_sanitize_text_strips_and_collapses() -> None:
    assert security.sanitize_text("  hello   world  ") == "hello world"


def test_sanitize_text_truncates() -> None:
    long = "x" * 2000
    assert len(security.sanitize_text(long, max_length=100)) == 100


def test_generate_secure_token_unique() -> None:
    a = security.generate_secure_token()
    b = security.generate_secure_token()
    assert a != b
    assert len(a) > 0


def test_mask_phone_long() -> None:
    masked = security.mask_phone("+998901234567")
    assert masked.endswith("67")
    assert "•" in masked


def test_is_safe_int_valid() -> None:
    assert security.is_safe_int("123") is True
    assert security.is_safe_int("-5") is True


def test_is_safe_int_invalid() -> None:
    assert security.is_safe_int("12.5") is False
    assert security.is_safe_int("abc") is False
    assert security.is_safe_int("") is False
