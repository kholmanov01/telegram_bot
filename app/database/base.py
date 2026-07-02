"""SQLAlchemy declarative base and shared mixins."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Provides a ``metadata`` registry shared by every model and Alembic's
    autogenerate feature.
    """

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        """Serialize the model instance to a plain dict.

        Args:
            exclude: Optional set of attribute names to omit.

        Returns:
            A dictionary representation of the model.
        """
        exclude = exclude or set()
        return {
            col.name: getattr(self, col.name)
            for col in self.__table__.columns  # type: ignore[attr-defined]
            if col.name not in exclude
        }


class TimestampMixin:
    """Mixin adding ``created_at`` / ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
