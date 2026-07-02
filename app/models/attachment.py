"""Attachment model — files / photos / documents linked to a task.

Admins can attach files during task creation; employees can attach proof
files (e.g. screenshots) when working on or completing a task. Attachments
are stored by their Telegram ``file_id`` so the bot can re-send them
without re-downloading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class Attachment(Base, TimestampMixin):
    """A file attached to a task (photo, document, video, audio, voice).

    The actual file bytes live on Telegram's servers; we only store the
    ``file_id`` (which is stable per bot) plus metadata for display.
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Telegram file identifiers (file_id is bot-specific but stable).
    file_id: Mapped[str] = mapped_column(String(512), nullable=False)
    file_unique_id: Mapped[str] = mapped_column(String(256), nullable=False)

    # One of: photo, document, video, audio, voice, animation.
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Original filename (for documents) or None (for photos).
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # File size in bytes (may be None for some media types).
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Optional caption accompanying the file.
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Mime type if available (e.g. "image/jpeg", "application/pdf").
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Who uploaded the file.
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- Relationships ---
    task: Mapped["Task"] = relationship(back_populates="attachments")
    uploader: Mapped[Optional["User"]] = relationship(foreign_keys=[uploaded_by])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Attachment id={self.id} task={self.task_id} type={self.file_type}>"
