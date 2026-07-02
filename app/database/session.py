"""Async SQLAlchemy engine, session factory and lifecycle helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import settings


def _create_engine() -> AsyncEngine:
    """Build the async engine tuned for production use.

    Uses connection-pool tuning for PostgreSQL and a lighter configuration
    for SQLite (which does not support ``pool_size`` / ``max_overflow`` and
    is typically used for development / demos).
    """
    url = settings.sqlalchemy_database_url
    if url.startswith("sqlite"):
        return create_async_engine(
            url,
            echo=False,
            future=True,
            # SQLite needs check_same_thread=False for async usage.
            connect_args={"check_same_thread": False},
        )
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_timeout=30,
        future=True,
    )


# Single shared engine & session factory for the whole application.
engine: AsyncEngine = _create_engine()

async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an :class:`AsyncSession` within a transactional context.

    Commits on success, rolls back on exception, and always closes the session.

    Yields:
        An open :class:`AsyncSession` instance.
    """
    session = async_session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Verify connectivity to the database (used on startup).

    Does NOT create tables — schema management is handled by Alembic.
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
