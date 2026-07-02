"""Settings service — key/value application configuration.

Wraps :class:`SettingRepository` with audit logging. The
:meth:`get_working_hours` helper prefers DB-stored values (so admins can
change them at runtime) and falls back to the env defaults from the
:class:`Settings` singleton when the DB keys are absent.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings as app_settings
from app.database.session import get_session
from app.models.enums import AuditAction
from app.models.setting import Setting
from app.repositories.audit_log import AuditLogRepository
from app.repositories.setting import SettingRepository
from app.utils.dates import now_utc


class SettingsService:
    """Read and write application settings stored in the database."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "SettingsService":
        """Return an instance bound to ``session`` for in-transaction use."""
        instance = cls()
        instance._session = session
        return instance

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[AsyncSession]:
        """Yield a usable session (injected or freshly opened)."""
        if self._session is not None:
            yield self._session
        else:
            async with get_session() as session:
                yield session

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def get(
        self, key: str, default: str | None = None
    ) -> str | None:
        """Return the value of a setting, or ``default`` if absent."""
        async with self._session_scope() as session:
            repo = SettingRepository(session)
            return await repo.get_value(key, default)

    async def set(
        self,
        key: str,
        value: str,
        description: str | None = None,
    ) -> None:
        """Upsert a setting and log a ``SETTINGS_UPDATED`` audit entry.

        Args:
            key: Unique setting key.
            value: New value.
            description: Optional human-readable description.
        """
        async with self._session_scope() as session:
            repo = SettingRepository(session)
            audit_repo = AuditLogRepository(session)

            setting = await repo.upsert(key, value, description)

            await audit_repo.create(
                {
                    "action": AuditAction.SETTINGS_UPDATED,
                    "target_type": "setting",
                    "target_id": setting.id,
                    "summary": f"Setting {key!r} updated",
                    "detail": {
                        "key": key,
                        "value": value,
                        "description": description,
                    },
                    "occurred_at": now_utc(),
                }
            )

            logger.info("Updated setting key={!r}", key)

    async def get_all(self) -> list[Setting]:
        """Return all settings ordered by key ascending."""
        async with self._session_scope() as session:
            repo = SettingRepository(session)
            return await repo.get_all()

    async def get_working_hours(self) -> tuple[str, str]:
        """Return the configured working-hours window as ``(start, end)``.

        Prefers DB-stored values under keys ``working_hours_start`` and
        ``working_hours_end``; falls back to the env defaults
        (``settings.working_hours_start`` / ``working_hours_end``) when
        either DB key is missing.
        """
        async with self._session_scope() as session:
            repo = SettingRepository(session)
            start = await repo.get_value("working_hours_start")
            end = await repo.get_value("working_hours_end")

        start = start or app_settings.working_hours_start
        end = end or app_settings.working_hours_end
        return start, end
