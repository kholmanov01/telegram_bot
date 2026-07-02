"""Tests for callback data factories and reply menu keyboards."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

from app.bot.keyboards import admin as admin_kb
from app.bot.keyboards import employee as employee_kb
from app.bot.keyboards.callbacks import (
    ConfirmCallback,
    EmployeeCallback,
    MenuCallback,
    PaginationCallback,
    PriorityCallback,
    SettingsCallback,
    StatsCallback,
    TaskCallback,
)
from app.models.enums import UserRole
from app.bot.keyboards.common import main_menu_keyboard


def test_task_callback_roundtrip() -> None:
    cb = TaskCallback(action="complete", task_id="42")
    packed = cb.pack()
    parsed = TaskCallback.unpack(packed)
    assert parsed.action == "complete"
    assert parsed.task_id == "42"


def test_employee_callback_roundtrip() -> None:
    cb = EmployeeCallback(action="view", employee_id="7")
    parsed = EmployeeCallback.unpack(cb.pack())
    assert parsed.action == "view"
    assert parsed.employee_id == "7"


def test_priority_callback_roundtrip() -> None:
    cb = PriorityCallback(priority="urgent")
    parsed = PriorityCallback.unpack(cb.pack())
    assert parsed.priority == "urgent"


def test_pagination_callback_roundtrip() -> None:
    cb = PaginationCallback(page="2", scope="tasks")
    parsed = PaginationCallback.unpack(cb.pack())
    assert parsed.page == "2"
    assert parsed.scope == "tasks"


def test_stats_callback_roundtrip() -> None:
    cb = StatsCallback(period="weekly")
    parsed = StatsCallback.unpack(cb.pack())
    assert parsed.period == "weekly"


def test_settings_callback_roundtrip() -> None:
    cb = SettingsCallback(action="edit", key="timezone")
    parsed = SettingsCallback.unpack(cb.pack())
    assert parsed.action == "edit"
    assert parsed.key == "timezone"


def test_confirm_callback_supports_colon_payload() -> None:
    """ConfirmCallback uses sep='|' so payloads may contain ':'."""
    cb = ConfirmCallback(action="yes", payload="archive:42")
    parsed = ConfirmCallback.unpack(cb.pack())
    assert parsed.action == "yes"
    assert parsed.payload == "archive:42"


def test_menu_callback_roundtrip() -> None:
    cb = MenuCallback(action="back")
    parsed = MenuCallback.unpack(cb.pack())
    assert parsed.action == "back"


def test_admin_menu_has_all_buttons() -> None:
    kb = admin_kb.admin_menu()
    labels: list[str] = []
    for row in kb.keyboard:
        labels.extend(b.text for b in row)
    joined = " ".join(labels)
    for expected in ["➕ Yangi vazifa", "👥 Xodimlar", "📋 Barcha vazifalar", "📈 Statistika", "⚙ Sozlamalar"]:
        assert expected in joined


def test_employee_menu_has_all_buttons() -> None:
    kb = employee_kb.employee_menu()
    labels: list[str] = []
    for row in kb.keyboard:
        labels.extend(b.text for b in row)
    joined = " ".join(labels)
    for expected in ["📌 Mening vazifalarim", "✅ Bajarilganlar", "📅 Bugun", "🔔 Eslatmalar", "⚙ Profil"]:
        assert expected in joined


def test_main_menu_dispatches_by_role() -> None:
    admin_kb_row = main_menu_keyboard(UserRole.SUPER_ADMIN)
    emp_kb_row = main_menu_keyboard(UserRole.EMPLOYEE)
    # Admin keyboard should mention "New Task", employee should mention "My Tasks"
    def first_texts(kb) -> str:
        out = []
        for row in kb.keyboard:
            out.extend(b.text for b in row)
        return " ".join(out)
    assert "Yangi vazifa" in first_texts(admin_kb_row)
    assert "Mening vazifalarim" in first_texts(emp_kb_row)


def test_priority_inline_has_four_buttons() -> None:
    kb = admin_kb.priority_inline()
    total = sum(len(row) for row in kb.inline_keyboard)
    assert total == 4
