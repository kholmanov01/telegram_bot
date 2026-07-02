"""User model — Telegram-registered accounts (admins & employees)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.employee import Employee


class User(Base, TimestampMixin):
    """A registered Telegram user.

    A user is either a Super Admin (bootstrapped from ``SUPER_ADMIN_IDS``) or
    an Employee (linked to an :class:`Employee` record via the ``employee``
    relationship after successful registration with an employee code).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Telegram numeric identifier (64-bit safe).
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )

    # Telegram-provided profile fields.
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Authorization.
    role: Mapped[UserRole] = mapped_column(String(32), 
        default=UserRole.EMPLOYEE, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_registered: Mapped[bool] = mapped_column(default=False, nullable=False)

    # When the user first interacted with the bot and last activity.
    registration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relationships ---
    employee: Mapped[Optional["Employee"]] = relationship(
        back_populates="user",
        uselist=False,
        foreign_keys="Employee.user_id",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="actor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} tg={self.telegram_id} role={self.role}>"
