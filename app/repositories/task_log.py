"""Repository for the :class:`TaskLog` aggregate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_log import TaskLog
from app.repositories.base import BaseRepository


class TaskLogRepository(BaseRepository[TaskLog]):
    """Data-access layer for :class:`TaskLog` records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a session and the TaskLog model."""
        super().__init__(session, TaskLog)

    async def get_for_task(self, task_id: int) -> list[TaskLog]:
        """Return all log entries for a task ordered by occurrence time ascending.

        Args:
            task_id: Related task id.

        Returns:
            List of task log entries.
        """
        stmt = (
            select(TaskLog)
            .where(TaskLog.task_id == task_id)
            .order_by(TaskLog.occurred_at.asc(), TaskLog.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(self, limit: int = 50) -> list[TaskLog]:
        """Return the most recent task log entries across all tasks.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of recent task log entries ordered by id descending.
        """
        stmt = select(TaskLog).order_by(TaskLog.id.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
