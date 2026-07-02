"""FSM states for task creation, attachment and search flows.

Task creation is a multi-step wizard:

    title → description → attachment_choice → (attachment)? → employee →
    priority → date → time → timezone → confirm

Each step waits for one atomic piece of input from the user.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup

__all__ = [
    "TaskCreationStates",
    "TaskSearchStates",
    "TaskAttachmentStates",
]


class TaskCreationStates(StatesGroup):
    """States of the admin task-creation wizard."""

    waiting_title = State()
    waiting_description = State()
    waiting_attachment_choice = State()
    waiting_attachment = State()
    waiting_employee = State()
    waiting_priority = State()
    waiting_date = State()
    waiting_time = State()
    waiting_timezone = State()
    waiting_confirm = State()


class TaskSearchStates(StatesGroup):
    """States of the task search flow."""

    waiting_query = State()


class TaskAttachmentStates(StatesGroup):
    """States of the add-attachment-to-existing-task flow."""

    waiting_file = State()
