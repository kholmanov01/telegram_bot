"""Audit log model — global, append-only record of every state-changing action."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import AuditAction

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base, TimestampMixin):
    """Immutable audit trail entry.

    Every meaningful action (login, task create/complete/expire, notification
    sent, settings change, ...) appends a row here.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    action: Mapped[AuditAction] = mapped_column(String(32), nullable=False, index=True)

    # Who performed the action.
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True
    )

    # Optional target entity (polymorphic by string type).
    target_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Human-readable summary and structured detail (JSON string).
    summary: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Where the action originated.
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # --- Relationships ---
    actor: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog id={self.id} action={self.action}>"
