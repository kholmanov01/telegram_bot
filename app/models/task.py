"""Task model — the core domain entity."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import TaskPriority, TaskStatus

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.notification import Notification
    from app.models.task_log import TaskLog
    from app.models.user import User


class Task(Base, TimestampMixin):
    """A task assigned by an admin to an employee."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        default=TaskStatus.PENDING, nullable=False, index=True
    )
    priority: Mapped[TaskPriority] = mapped_column(
        default=TaskPriority.MEDIUM, nullable=False, index=True
    )

    # Deadline stored as timezone-aware UTC.
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Assignment.
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Lifecycle timestamps.
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Which reminders have already been sent (JSON would be simpler but we
    # store a comma-separated set to keep the column primitive per project rules).
    sent_reminders: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Admin note when completing / expiring.
    completion_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    employee: Mapped["Employee"] = relationship(back_populates="tasks", foreign_keys=[employee_id])
    assigner: Mapped["User"] = relationship(foreign_keys=[assigned_by])
    logs: Mapped[list["TaskLog"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task id={self.id} status={self.status} title={self.title!r}>"
