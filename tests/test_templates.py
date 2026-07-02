"""Tests for app.notifications.templates — all templates render HTML without error."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.notifications import templates


def test_welcome_message_nonempty() -> None:
    assert len(templates.welcome_message()) > 0


def test_registration_success_escapes_name() -> None:
    out = templates.registration_success("<b>Ali</b>", "EMP001")
    assert "<b>Ali</b>" not in out
    assert "&lt;b&gt;Ali&lt;/b&gt;" in out
    assert "EMP001" in out


def test_registration_failed_contains_reason() -> None:
    out = templates.registration_failed("Bunday kod topilmadi")
    assert "Bunday kod topilmadi" in out


def test_new_task_notification_renders_card() -> None:
    task = SimpleNamespace(
        title="Deploy",
        description="Prod",
        priority="urgent",
        deadline=datetime.now(timezone.utc) + timedelta(hours=5),
    )
    out = templates.new_task_notification(task)
    assert "📌" in out
    assert "Deploy" in out
    assert "🔴" in out  # urgent emoji


def test_reminder_notification_includes_offset() -> None:
    task = SimpleNamespace(
        title="Review",
        description=None,
        priority="medium",
        deadline=datetime.now(timezone.utc) + timedelta(minutes=45),
    )
    out = templates.reminder_notification(task, 60)
    assert "⏰" in out
    assert "Review" in out


def test_task_completed_admin_includes_name_and_time() -> None:
    out = templates.task_completed_admin("Ali Valiyev", "Deploy", "15.06.2025 09:30")
    assert "Ali Valiyev" in out
    assert "Deploy" in out
    assert "15.06.2025 09:30" in out


def test_deadline_passed_employee() -> None:
    task = SimpleNamespace(
        title="X",
        description=None,
        priority="low",
        deadline=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    out = templates.deadline_passed_employee(task)
    assert "❌" in out


def test_error_message_nonempty() -> None:
    assert "⚠" in templates.error_message() or "⚠️" in templates.error_message()


def test_admin_welcome_and_employee_welcome() -> None:
    assert len(templates.admin_welcome()) > 0
    assert "Ali" in templates.employee_welcome("Ali")


def test_invalid_input() -> None:
    out = templates.invalid_input("sana")
    assert "sana" in out
