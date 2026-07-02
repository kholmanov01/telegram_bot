"""ORM models package.

Importing this package registers every model on the shared ``Base.metadata``
so that Alembic autogenerate and ``selectinload`` relationships work.
"""

from app.database.base import Base
from app.models.enums import (
    AuditAction,
    NotificationStatus,
    NotificationType,
    TaskPriority,
    TaskStatus,
    UserRole,
)
from app.models.user import User
from app.models.employee import Employee
from app.models.task import Task
from app.models.notification import Notification
from app.models.task_log import TaskLog
from app.models.audit_log import AuditLog
from app.models.setting import Setting
from app.models.attachment import Attachment

__all__ = [
    "Base",
    "User",
    "Employee",
    "Task",
    "Notification",
    "TaskLog",
    "AuditLog",
    "Setting",
    "Attachment",
    "UserRole",
    "TaskStatus",
    "TaskPriority",
    "NotificationType",
    "NotificationStatus",
    "AuditAction",
]
