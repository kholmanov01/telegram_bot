"""FSM state groups for the bot's conversational flows."""

from __future__ import annotations

from app.bot.states.employee import EmployeeCreationStates, EmployeeEditStates
from app.bot.states.registration import RegistrationStates
from app.bot.states.task import TaskCreationStates, TaskSearchStates

__all__ = [
    "RegistrationStates",
    "TaskCreationStates",
    "TaskSearchStates",
    "EmployeeCreationStates",
    "EmployeeEditStates",
]
