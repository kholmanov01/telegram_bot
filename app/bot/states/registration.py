"""FSM states for the employee-registration flow.

Used after ``/start`` for users that are not yet registered. The user is
asked to enter their employee code (e.g. ``EMP001``); on success an
:class:`app.models.user.User` is linked to the matching
:class:`app.models.employee.Employee`.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup

__all__ = ["RegistrationStates"]


class RegistrationStates(StatesGroup):
    """States traversed during the employee self-registration flow."""

    waiting_employee_code = State()
