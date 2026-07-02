"""Repository for the :class:`AuditLog` aggregate."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Data-access layer for :class:`AuditLog` records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a session and the AuditLog model."""
        super().__init__(session, AuditLog)

    async def create(self, data: dict[str, Any]) -> AuditLog:
        """Insert a new audit-log entry.

        Automatically serialises the ``detail`` field to a JSON string when
        a dict (or other non-string object) is provided, so callers can pass
        structured payloads directly without worrying about the ``Text``
        column type.
        """
        detail = data.get("detail")
        if detail is not None and not isinstance(detail, str):
            data = {**data, "detail": json.dumps(detail, ensure_ascii=False, default=str)}
        return await super().create(data)

    async def get_recent(self, limit: int = 100) -> list[AuditLog]:
        """Return the most recent audit log entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of recent audit entries ordered by id descending.
        """
        stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_actor(self, actor_id: int, limit: int = 50) -> list[AuditLog]:
        """Return audit entries produced by the given actor.

        Args:
            actor_id: User id of the actor.
            limit: Maximum number of entries to return.

        Returns:
            List of audit entries for the actor ordered by id descending.
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_action(
        self, action: AuditAction, limit: int = 100
    ) -> list[AuditLog]:
        """Return audit entries matching the given action.

        Args:
            action: Action type to filter by.
            limit: Maximum number of entries to return.

        Returns:
            List of audit entries for the action ordered by id descending.
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
