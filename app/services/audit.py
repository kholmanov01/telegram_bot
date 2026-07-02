"""Audit service — writes immutable audit-log entries.

Every state-changing action in the application is recorded via
:class:`AuditService`. The service supports two execution modes:

* **Default (standalone):** each call to :meth:`log` opens its own
  session via :func:`get_session` and commits immediately.
* **In-transaction:** construct with :meth:`with_session` to bind the
  service to a session already managed by the caller. Writes are then
  committed (or rolled back) by the caller's transaction boundary.

The ``detail`` dict is serialised to JSON before storage so that the
``AuditLog.detail`` column (``Text``) holds a stable, queryable string.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.models.enums import AuditAction
from app.repositories.audit_log import AuditLogRepository
from app.utils.dates import now_utc


class AuditService:
    """Write audit-log entries recording who did what to which entity."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "AuditService":
        """Return an instance bound to ``session`` for in-transaction use.

        When constructed this way the service does NOT commit or close the
        session — that responsibility belongs to the caller.
        """
        instance = cls()
        instance._session = session
        return instance

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[AsyncSession]:
        """Yield a usable session.

        If a session was injected via :meth:`with_session` it is yielded
        as-is (the caller owns its lifecycle). Otherwise a fresh
        transactional session is opened via :func:`get_session`.
        """
        if self._session is not None:
            yield self._session
        else:
            async with get_session() as session:
                yield session

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def log(
        self,
        action: AuditAction,
        actor_id: int | None = None,
        actor_telegram_id: int | None = None,
        target_type: str | None = None,
        target_id: int | None = None,
        summary: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Append a single audit-log entry.

        Args:
            action: The :class:`AuditAction` performed.
            actor_id: User id of the actor (``None`` for system actions).
            actor_telegram_id: Telegram id of the actor (denormalised for
                resilience when the user row is later deleted).
            target_type: Short string naming the target entity type
                (e.g. ``"task"``, ``"employee"``).
            target_id: Primary key of the target entity.
            summary: Short human-readable description of the action.
            detail: Optional structured payload — serialised to JSON.
        """
        detail_json: str | None = None
        if detail is not None:
            try:
                detail_json = json.dumps(
                    detail, ensure_ascii=False, default=str
                )
            except (TypeError, ValueError):
                detail_json = None

        async with self._session_scope() as session:
            repo = AuditLogRepository(session)
            await repo.create(
                {
                    "action": action,
                    "actor_id": actor_id,
                    "actor_telegram_id": actor_telegram_id,
                    "target_type": target_type,
                    "target_id": target_id,
                    "summary": summary,
                    "detail": detail_json,
                    "occurred_at": now_utc(),
                }
            )
            logger.info(
                "Audit: action={} actor={} target={}/{} summary={!r}",
                getattr(action, "value", action),
                actor_id,
                target_type,
                target_id,
                summary,
            )
