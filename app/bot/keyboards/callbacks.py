"""Aiogram :class:`CallbackData` factories for every inline button.

Every inline button in the bot MUST use one of these factories — never raw
string parsing — so callback payloads stay short, typed and easy to route.

Naming conventions:
- ``action`` fields use short snake_case verbs (``view``, ``complete`` ...).
- ``task_id`` / ``employee_id`` are passed as strings (aiogram requires
  ``str`` payload fields) but contain the integer primary key.
- ``payload`` is an opaque string used by :class:`ConfirmCallback` to carry
  the original intent (e.g. ``"archive:42"``).
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

__all__ = [
    "TaskCallback",
    "EmployeeCallback",
    "PriorityCallback",
    "PaginationCallback",
    "StatsCallback",
    "SettingsCallback",
    "ConfirmCallback",
    "MenuCallback",
    "AttachmentCallback",
]


class TaskCallback(CallbackData, prefix="t"):
    """Inline buttons acting on a single task.

    Actions:
        - ``view``      — open task card
        - ``complete``  — mark task as completed
        - ``details``   — show full task details (description, logs ...)
        - ``archive``   — archive the task (admin only)
        - ``restore``   — restore an archived task (admin only)
        - ``cancel``    — cancel an in-flight operation on the task
    """

    action: str
    task_id: str


class EmployeeCallback(CallbackData, prefix="e"):
    """Inline buttons acting on a single employee.

    Actions:
        - ``view``       — show employee profile
        - ``tasks``      — list tasks assigned to the employee
        - ``deactivate`` — deactivate the employee (admin only)
        - ``activate``   — re-activate the employee (admin only)
    """

    action: str
    employee_id: str


class PriorityCallback(CallbackData, prefix="p"):
    """Inline button used to pick a task priority (low / medium / high / urgent)."""

    priority: str


class PaginationCallback(CallbackData, prefix="pg"):
    """Inline button for paginated lists.

    ``scope`` distinguishes the listing context (e.g. ``tasks``,
    ``completed``, ``employees``, ``search``) so the handler can re-route.
    """

    page: str
    scope: str


class StatsCallback(CallbackData, prefix="s"):
    """Inline button to select a statistics period.

    Values: ``daily``, ``weekly``, ``monthly``, ``overall``, ``employee``.
    """

    period: str


class SettingsCallback(CallbackData, prefix="st"):
    """Inline buttons for the settings panel.

    Actions:
        - ``set``  — open editor for a setting ``key``
        - ``edit`` — apply an edited value
        - ``back`` — return to the settings root
    """

    action: str
    key: str


class ConfirmCallback(CallbackData, prefix="c", sep="|"):
    """Yes/No confirmation inline buttons.

    ``action`` is ``yes`` or ``no``; ``payload`` carries the operation to
    confirm (e.g. ``"archive:42"`` or ``"deactivate:7"``).

    Note: aiogram's default separator (``:``) is replaced with ``|`` here so
    the payload may itself contain colons — this keeps the payload readable
    (e.g. ``"archive:42"``) without colliding with aiogram's parser.
    """

    action: str
    payload: str


class MenuCallback(CallbackData, prefix="m"):
    """Generic menu-navigation inline button.

    ``action`` is a short verb such as ``back``, ``home``, ``tasks`` ... that
    the handler router will switch on.
    """

    action: str


class AttachmentCallback(CallbackData, prefix="att"):
    """Inline buttons for task attachments.

    Actions:
        - ``view`` — list attachments of the task
        - ``add``  — start adding a new file to the task
        - ``back`` — return from the attachment view to the task card
    """

    action: str
    task_id: str


# --------------------------------------------------------------------------- #
# Type alias used by keyboard builders
# --------------------------------------------------------------------------- #
InlineMarkup = InlineKeyboardMarkup
