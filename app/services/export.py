"""Export service — produces Excel/PDF byte blobs for download.

Thin orchestration layer that loads tasks via :class:`TaskService` and
hands them to the low-level byte producers in :mod:`app.utils.export`.

The heavy third-party imports (``openpyxl``, ``reportlab``) are deferred
inside the utility functions, so importing this module is cheap and
works even when those libraries are absent (e.g. during ``py_compile``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.models.enums import TaskPriority, TaskStatus
from app.utils.export import (
    stats_to_excel_bytes,
    tasks_to_excel_bytes,
    tasks_to_pdf_bytes,
)


class ExportService:
    """Build downloadable Excel/PDF documents from DB data."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "ExportService":
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
    async def export_tasks_excel(
        self,
        employee_id: int | None = None,
        status: TaskStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> bytes:
        """Return an ``.xlsx`` byte blob of tasks matching the filters.

        Args:
            employee_id: Optional employee filter.
            status: Optional status filter.
            date_from: Optional inclusive lower bound on the deadline.
            date_to: Optional inclusive upper bound on the deadline.

        Returns:
            ``.xlsx`` file content as bytes.
        """
        # Local import avoids a circular dependency at module load time
        # (TaskService imports nothing from this module, but keeping the
        # import local is the safe pattern for cross-service calls).
        from app.services.task import TaskService

        tasks = await TaskService().get_all_filtered(
            employee_id=employee_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            limit=10000,
            offset=0,
        )
        logger.info(
            "Exporting {} tasks to Excel", len(tasks)
        )
        return tasks_to_excel_bytes(tasks)

    async def export_tasks_pdf(
        self,
        employee_id: int | None = None,
        status: TaskStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> bytes:
        """Return a PDF byte blob of tasks matching the filters.

        Args:
            employee_id: Optional employee filter.
            status: Optional status filter.
            date_from: Optional inclusive lower bound on the deadline.
            date_to: Optional inclusive upper bound on the deadline.

        Returns:
            PDF file content as bytes.
        """
        from app.services.task import TaskService

        tasks = await TaskService().get_all_filtered(
            employee_id=employee_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            limit=10000,
            offset=0,
        )
        logger.info(
            "Exporting {} tasks to PDF", len(tasks)
        )
        return tasks_to_pdf_bytes(tasks)

    async def export_statistics_excel(self, stats: dict) -> bytes:
        """Return an ``.xlsx`` byte blob of a statistics dict.

        Args:
            stats: Mapping of statistic name to value (as produced by
                :class:`StatisticsService`).

        Returns:
            ``.xlsx`` file content as bytes.
        """
        logger.info("Exporting statistics to Excel")
        return stats_to_excel_bytes(stats)
