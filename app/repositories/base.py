"""Generic asynchronous repository base class.

Implements common CRUD operations using SQLAlchemy 2.0 async style. Concrete
repositories subclass :class:`BaseRepository` and add entity-specific queries.
"""

from __future__ import annotations

from typing import Any, Generic, Type, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic CRUD repository.

    Args:
        session: An open :class:`AsyncSession`.
        model: The SQLAlchemy model class managed by this repository.
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]) -> None:
        self.session: AsyncSession = session
        self.model: Type[ModelType] = model

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    async def get_by_id(self, id_: int) -> ModelType | None:
        """Return the entity with the given primary key, or ``None``."""
        return await self.session.get(self.model, id_)

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[ModelType]:
        """Return a page of all entities ordered by id descending."""
        stmt = select(self.model).order_by(self.model.id.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Return the total number of rows for this entity."""
        result = await self.session.execute(select(func.count()).select_from(self.model))
        return int(result.scalar_one())

    async def find_one(self, **filters: Any) -> ModelType | None:
        """Return the first entity matching all keyword filters, or ``None``."""
        stmt = select(self.model)
        for key, value in filters.items():
            column = getattr(self.model, key, None)
            if column is None:
                raise AttributeError(f"{self.model.__name__} has no column {key!r}")
            stmt = stmt.where(column == value)
        result = await self.session.execute(stmt.limit(1))
        return result.scalars().first()

    async def find_many(self, limit: int = 100, offset: int = 0, **filters: Any) -> list[ModelType]:
        """Return all entities matching the keyword filters."""
        stmt = select(self.model)
        for key, value in filters.items():
            column = getattr(self.model, key, None)
            if column is None:
                raise AttributeError(f"{self.model.__name__} has no column {key!r}")
            stmt = stmt.where(column == value)
        stmt = stmt.order_by(self.model.id.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    async def create(self, data: dict[str, Any]) -> ModelType:
        """Insert a new entity from a dict of column values and return it."""
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, id_: int, data: dict[str, Any]) -> ModelType | None:
        """Update columns of the entity with the given id and return it."""
        stmt = update(self.model).where(self.model.id == id_).values(**data).returning(self.model)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if row is not None:
            await self.session.refresh(row)
        return row

    async def delete(self, id_: int) -> bool:
        """Delete the entity with the given id. Return True if a row was removed."""
        stmt = delete(self.model).where(self.model.id == id_)
        result = await self.session.execute(stmt)
        return result.rowcount > 0  # type: ignore[union-attr]

    async def save(self, obj: ModelType) -> ModelType:
        """Persist a tracked entity instance."""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
