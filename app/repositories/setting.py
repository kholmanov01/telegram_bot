"""Repository for the :class:`Setting` aggregate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import Setting
from app.repositories.base import BaseRepository


class SettingRepository(BaseRepository[Setting]):
    """Data-access layer for :class:`Setting` records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a session and the Setting model."""
        super().__init__(session, Setting)

    async def get_by_key(self, key: str) -> Setting | None:
        """Return the setting with the given key, or ``None`` if not present.

        Args:
            key: Unique setting key.

        Returns:
            The :class:`Setting` instance or ``None``.
        """
        stmt = select(Setting).where(Setting.key == key)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_value(self, key: str, default: str | None = None) -> str | None:
        """Return the value of a setting, or ``default`` if the key is missing.

        Args:
            key: Unique setting key.
            default: Fallback value when the key does not exist.

        Returns:
            The stored value, or ``default``.
        """
        setting = await self.get_by_key(key)
        if setting is None:
            return default
        return setting.value

    async def upsert(
        self,
        key: str,
        value: str,
        description: str | None = None,
        is_system: bool = False,
    ) -> Setting:
        """Insert or update a setting by key.

        If a setting with the given key exists, its ``value`` (and optionally
        ``description`` / ``is_system``) is updated. Otherwise a new row is
        inserted. The persisted instance is returned.

        Args:
            key: Unique setting key.
            value: Setting value.
            description: Optional human-readable description.
            is_system: Whether the setting is system-managed.

        Returns:
            The upserted :class:`Setting` instance.
        """
        setting = await self.get_by_key(key)
        if setting is None:
            data = {
                "key": key,
                "value": value,
                "description": description,
                "is_system": is_system,
            }
            return await self.create(data)

        setting.value = value
        if description is not None:
            setting.description = description
        setting.is_system = is_system
        return await self.save(setting)

    async def get_all(self) -> list[Setting]:
        """Return all settings ordered by key ascending."""
        stmt = select(Setting).order_by(Setting.key.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
