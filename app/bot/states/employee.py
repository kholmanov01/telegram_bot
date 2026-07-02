"""FSM states for the employee creation & edit flows.

Employee creation is a 4-step wizard:

    full_name → position → department → phone

The edit flow reuses the same fields but starts from an existing employee.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup

__all__ = ["EmployeeCreationStates", "EmployeeEditStates"]


class EmployeeCreationStates(StatesGroup):
    """States of the admin employee-creation wizard."""

    waiting_full_name = State()
    waiting_position = State()
    waiting_department = State()
    waiting_phone = State()


class EmployeeEditStates(StatesGroup):
    """States of the admin employee-edit flow."""

    waiting_full_name = State()
    waiting_position = State()
    waiting_department = State()
    waiting_phone = State()
    waiting_active = State()
