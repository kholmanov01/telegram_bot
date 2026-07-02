"""Repository for the :class:`Attachment` aggregate.

Attachments are files (photos, documents, videos, audio, voice, animations)
linked to a task and stored by their Telegram ``file_id``.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment
from app.repositories.base import BaseRepository


class AttachmentRepository(BaseRepository[Attachment]):
    """Data-access layer for :class:`Attachment` records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a session and the Attachment model."""
        super().__init__(session, Attachment)

    async def get_for_task(self, task_id: int) -> list[Attachment]:
        """Return all attachments for the given task ordered by id ascending.

        Args:
            task_id: Primary key of the task.

        Returns:
            List of attachments ordered from oldest to newest.
        """
        stmt = (
            select(Attachment)
            .where(Attachment.task_id == task_id)
            .order_by(Attachment.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_task(self, task_id: int) -> int:
        """Return the number of attachments linked to the given task.

        Args:
            task_id: Primary key of the task.

        Returns:
            Integer count (``0`` if the task has no attachments).
        """
        stmt = (
            select(func.count())
            .select_from(Attachment)
            .where(Attachment.task_id == task_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
