"""Repository for the :class:`Notification` aggregate."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationStatus, NotificationType
from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    """Data-access layer for :class:`Notification` records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a session and the Notification model."""
        super().__init__(session, Notification)

    async def get_pending_for_task(
        self, task_id: int, type: NotificationType
    ) -> list[Notification]:
        """Return notifications for a task of the given type still in PENDING status.

        Args:
            task_id: Related task id.
            type: Notification type filter.

        Returns:
            List of matching notifications ordered by id ascending.
        """
        stmt = (
            select(Notification)
            .where(
                Notification.task_id == task_id,
                Notification.type == type,
                Notification.status == NotificationStatus.PENDING,
            )
            .order_by(Notification.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_sent(self, notification_id: int) -> None:
        """Mark a notification as successfully SENT and record the sent timestamp.

        Args:
            notification_id: Primary key of the notification.
        """
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id)
            .values(
                status=NotificationStatus.SENT,
                sent_at=datetime.now(timezone.utc),
                error=None,
            )
        )
        await self.session.execute(stmt)

    async def mark_failed(self, notification_id: int, error: str) -> None:
        """Mark a notification as FAILED and store the error message.

        Args:
            notification_id: Primary key of the notification.
            error: Error description.
        """
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id)
            .values(
                status=NotificationStatus.FAILED,
                error=error,
                sent_at=datetime.now(timezone.utc),
            )
        )
        await self.session.execute(stmt)

    async def get_recent(self, limit: int = 50) -> list[Notification]:
        """Return the most recent notifications ordered by id descending.

        Args:
            limit: Maximum number of notifications to return.

        Returns:
            List of recent notifications.
        """
        stmt = select(Notification).order_by(Notification.id.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
