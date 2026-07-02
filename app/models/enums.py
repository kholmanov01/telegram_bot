"""Enumerations shared across models and the service layer.

Using ``str, Enum`` so SQLAlchemy stores readable string values and
serialisation to JSON is straightforward.
"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """User roles. There are exactly two roles in the system."""

    SUPER_ADMIN = "super_admin"
    EMPLOYEE = "employee"


class TaskStatus(str, Enum):
    """Lifecycle states of a task."""

    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class TaskPriority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    @property
    def emoji(self) -> str:
        """Return an emoji representing the priority level."""
        return {
            TaskPriority.LOW: "🟢",
            TaskPriority.MEDIUM: "🟡",
            TaskPriority.HIGH: "🟠",
            TaskPriority.URGENT: "🔴",
        }[self]

    @property
    def label(self) -> str:
        """Return a human-readable label for the priority."""
        return {
            TaskPriority.LOW: "Low",
            TaskPriority.MEDIUM: "Medium",
            TaskPriority.HIGH: "High",
            TaskPriority.URGENT: "Urgent",
        }[self]


class NotificationType(str, Enum):
    """Types of notifications the bot can send."""

    NEW_TASK = "new_task"
    REMINDER = "reminder"
    DEADLINE_PASSED = "deadline_passed"
    TASK_COMPLETED = "task_completed"
    TASK_EXPIRED = "task_expired"
    SYSTEM = "system"


class NotificationStatus(str, Enum):
    """Delivery status of a notification."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class AuditAction(str, Enum):
    """Audit log action types — every state-changing action is logged."""

    EMPLOYEE_LOGIN = "employee_login"
    EMPLOYEE_REGISTERED = "employee_registered"
    EMPLOYEE_CREATED = "employee_created"
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_EXPIRED = "task_expired"
    TASK_ARCHIVED = "task_archived"
    TASK_RESTORED = "task_restored"
    NOTIFICATION_SENT = "notification_sent"
    SETTINGS_UPDATED = "settings_updated"
    LOGIN_FAILED = "login_failed"
