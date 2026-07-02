"""Repositories package.

Each repository encapsulates persistence concerns for a single aggregate,
exposing a clean, async, type-safe API to the service layer. Repositories
never contain business logic — only data access.
"""

from app.repositories.attachment import AttachmentRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.base import BaseRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.notification import NotificationRepository
from app.repositories.setting import SettingRepository
from app.repositories.task import TaskRepository
from app.repositories.task_log import TaskLogRepository
from app.repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "EmployeeRepository",
    "TaskRepository",
    "NotificationRepository",
    "TaskLogRepository",
    "AuditLogRepository",
    "SettingRepository",
    "AttachmentRepository",
]
