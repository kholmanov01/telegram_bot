"""Repository for the :class:`User` aggregate."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Data-access layer for :class:`User` records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a session and the User model."""
        super().__init__(session, User)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Return the user matching the Telegram id, or ``None`` if not found.

        Args:
            telegram_id: Telegram numeric user identifier.

        Returns:
            The :class:`User` instance or ``None``.
        """
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def count_by_role(self, role: UserRole) -> int:
        """Return the number of users with the given role.

        Args:
            role: One of :class:`UserRole`.

        Returns:
            Count of users for that role.
        """
        stmt = select(func.count()).select_from(User).where(User.role == role)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def touch_activity(self, user_id: int) -> None:
        """Update ``last_activity`` of the given user to the current UTC time.

        Args:
            user_id: Primary key of the user.
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(last_activity=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
