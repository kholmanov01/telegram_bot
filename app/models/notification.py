"""Notification model — tracks every message the bot sends to users."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import NotificationStatus, NotificationType

if TYPE_CHECKING:
    from app.models.task import Task


class Notification(Base, TimestampMixin):
    """A notification dispatched (or queued) by the bot.

    Keeping a record of every notification enables audit trails, retry logic
    and statistics on reminder throughput.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    type: Mapped[NotificationType] = mapped_column(nullable=False, index=True)
    status: Mapped[NotificationStatus] = mapped_column(
        default=NotificationStatus.PENDING, nullable=False, index=True
    )

    # Recipient (User) — denormalised telegram_id for resilience.
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_telegram_id: Mapped[Optional[int]] = mapped_column(
        nullable=True, index=True
    )

    task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Optional offset (in minutes before deadline) — used for reminders.
    reminder_offset_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)

    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    task: Mapped[Optional["Task"]] = relationship(back_populates="notifications")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Notification id={self.id} type={self.type} status={self.status}>"
