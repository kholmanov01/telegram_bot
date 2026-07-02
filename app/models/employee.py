"""Employee model — company staff managed by admins.

Each employee has a unique, human-readable code (``EMP001``) generated at
creation time. The employee is linked to a :class:`User` only after they
register in the bot using that code.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class Employee(Base, TimestampMixin):
    """A company employee created by a super admin."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Human-readable unique code, e.g. EMP001.
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Link to the Telegram user once the employee registers in the bot.
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    registered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Created by which admin (User id).
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Relationships ---
    user: Mapped[Optional["User"]] = relationship(
        back_populates="employee", foreign_keys=[user_id]
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Employee code={self.code} name={self.full_name!r}>"
