"""Task log model — per-task lifecycle history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task


class TaskLog(Base, TimestampMixin):
    """An immutable record of a single task lifecycle event.

    Unlike :class:`AuditLog` (which is global and actor-centric), the task log
    is task-centric and used to render the task "details / history" view.
    """

    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # What happened.
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional actor (User id) that triggered the event.
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Snapshot of status transition.
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # --- Relationships ---
    task: Mapped["Task"] = relationship(back_populates="logs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TaskLog task={self.task_id} action={self.action!r}>"
