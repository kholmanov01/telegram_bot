"""Setting model — key/value application settings (working hours, tz, language...).

The single active configuration row can be overridden by environment variables;
this table holds admin-editable runtime settings persisted across restarts.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class Setting(Base, TimestampMixin):
    """A single application setting stored as a key/value pair."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Some settings are admin-only editable.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Setting key={self.key!r} value={self.value!r}>"
