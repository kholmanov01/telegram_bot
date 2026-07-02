"""Services package.

Each service orchestrates one or more repositories behind a clean,
async, type-safe API. Services open their own sessions via
:func:`get_session` by default; pass an existing session to a service's
``with_session`` classmethod to participate in an outer transaction.

Public surface (consumed by handlers, middleware and the scheduler):

- :class:`AuditService`        — append-only audit trail writer.
- :class:`AuthService`         — user onboarding & employee registration.
- :class:`EmployeeService`     — employee CRUD & code generation.
- :class:`TaskService`         — task lifecycle & queries.
- :class:`StatisticsService`   — aggregate metrics & reports.
- :class:`NotificationService` — Telegram message dispatch & recording.
- :class:`ExportService`       — Excel/PDF byte producers.
- :class:`SettingsService`     — DB-backed application settings.
"""

from __future__ import annotations

from app.services.attachment import AttachmentService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.employee import EmployeeService
from app.services.export import ExportService
from app.services.notification import NotificationService
from app.services.settings import SettingsService
from app.services.statistics import StatisticsService
from app.services.task import TaskService

__all__ = [
    "AuditService",
    "AuthService",
    "EmployeeService",
    "TaskService",
    "StatisticsService",
    "NotificationService",
    "ExportService",
    "SettingsService",
    "AttachmentService",
]
