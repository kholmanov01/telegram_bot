"""Statistics service — aggregate task metrics for dashboards & reports.

Provides per-employee and overall statistics (counts, success rate,
average completion time) plus daily / weekly / monthly reports broken
down by priority.

All time ranges are computed in the application timezone
(``settings.app_timezone``) and converted to UTC for DB comparisons, so
that "today" means today for the user — not for the server's UTC clock.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, AsyncIterator

import pytz
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.session import get_session
from app.models.employee import Employee
from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.employee import EmployeeRepository
from app.repositories.task import TaskRepository
from app.utils.dates import now_local


class StatisticsService:
    """Compute aggregate metrics over tasks and employees."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "StatisticsService":
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
    # Formatting helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _format_avg_time(seconds: float) -> str:
        """Format an average completion time in seconds as a compact string.

        Examples: ``"2k 5s 30daqiqa"``, ``"19soniya"``, ``"—"``.
        """
        if seconds is None or seconds <= 0:
            return "—"
        total = int(seconds)
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        parts: list[str] = []
        if days > 0:
            parts.append(f"{days}k")
        if hours > 0:
            parts.append(f"{hours}s")
        if minutes > 0:
            parts.append(f"{minutes}daqiqa")
        if not parts:
            return f"{total}soniya"
        return " ".join(parts)

    @staticmethod
    def _compute_success_rate(completed: int, expired: int) -> float:
        """Return the success rate as a percentage (0-100).

        Computed as ``completed / (completed + expired) * 100``. When
        there are no completed-or-expired tasks the rate is ``0.0``.
        """
        total = completed + expired
        if total <= 0:
            return 0.0
        return round(completed / total * 100.0, 1)

    @staticmethod
    def _avg_seconds(times: list[tuple[Any, float]]) -> float:
        """Return the mean completion time from a list of ``(task, seconds)``."""
        if not times:
            return 0.0
        total = sum(seconds for _, seconds in times)
        return total / len(times)

    @staticmethod
    def _day_range(d: date) -> tuple[datetime, datetime]:
        """Return the UTC ``[start, end]`` of the given local date."""
        tz = pytz.timezone(settings.app_timezone)
        start_local = tz.localize(datetime.combine(d, time.min))
        end_local = tz.localize(datetime.combine(d, time.max))
        return (
            start_local.astimezone(timezone.utc),
            end_local.astimezone(timezone.utc),
        )

    @staticmethod
    def _week_range(d: date) -> tuple[date, date]:
        """Return the ``(monday, sunday)`` dates for the week containing ``d``."""
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday

    @staticmethod
    def _month_range(d: date) -> tuple[date, date]:
        """Return the ``(first, last)`` dates for the month containing ``d``."""
        first = d.replace(day=1)
        # Last day = first day of next month minus one day.
        if first.month == 12:
            next_first = first.replace(year=first.year + 1, month=1, day=1)
        else:
            next_first = first.replace(month=first.month + 1, day=1)
        last = next_first - timedelta(days=1)
        return first, last

    async def _count_in_range(
        self,
        session: AsyncSession,
        column: Any,
        start_utc: datetime,
        end_utc: datetime,
    ) -> int:
        """Count tasks where ``column`` falls within ``[start, end]`` UTC."""
        stmt = (
            select(func.count())
            .select_from(Task)
            .where(column >= start_utc, column <= end_utc)
        )
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def _count_by_priority_in_range(
        self,
        session: AsyncSession,
        column: Any,
        start_utc: datetime,
        end_utc: datetime,
    ) -> dict[str, int]:
        """Group-count tasks by priority where ``column`` is in range."""
        stmt = (
            select(Task.priority, func.count())
            .where(column >= start_utc, column <= end_utc)
            .group_by(Task.priority)
        )
        result = await session.execute(stmt)
        counts: dict[str, int] = {
            p.value: 0 for p in TaskPriority
        }
        for priority, count in result.all():
            key = (
                priority.value
                if hasattr(priority, "value")
                else str(priority)
            )
            if key in counts:
                counts[key] = int(count)
        return counts

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def employee_stats(self, employee_id: int) -> dict:
        """Return aggregate statistics for a single employee.

        Returns a dict with keys: ``completed``, ``expired``,
        ``pending``, ``success_rate`` (0-100 float), ``avg_completion_time``
        (human-readable string).
        """
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            counts = await task_repo.count_by_status(employee_id)
            completed = counts.get(TaskStatus.COMPLETED, 0)
            expired = counts.get(TaskStatus.EXPIRED, 0)
            pending = counts.get(TaskStatus.PENDING, 0)

            times = await task_repo.get_completion_times(employee_id)
            avg_seconds = self._avg_seconds(times)

            return {
                "completed": completed,
                "expired": expired,
                "pending": pending,
                "success_rate": self._compute_success_rate(
                    completed, expired
                ),
                "avg_completion_time": self._format_avg_time(avg_seconds),
            }

    async def overall_stats(self) -> dict:
        """Return aggregate statistics across the entire system.

        Returns a dict with keys: ``total``, ``completed``, ``expired``,
        ``pending``, ``success_rate``, ``avg_completion_time``,
        ``active_employees``, ``total_employees``.
        """
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            emp_repo = EmployeeRepository(session)

            counts = await task_repo.count_by_status(None)
            completed = counts.get(TaskStatus.COMPLETED, 0)
            expired = counts.get(TaskStatus.EXPIRED, 0)
            pending = counts.get(TaskStatus.PENDING, 0)
            archived = counts.get(TaskStatus.ARCHIVED, 0)
            total = completed + expired + pending + archived

            times = await task_repo.get_completion_times(None)
            avg_seconds = self._avg_seconds(times)

            active_employees = await emp_repo.get_active_employees()
            total_employees = await emp_repo.count()

            return {
                "total": total,
                "completed": completed,
                "expired": expired,
                "pending": pending,
                "archived": archived,
                "success_rate": self._compute_success_rate(
                    completed, expired
                ),
                "avg_completion_time": self._format_avg_time(avg_seconds),
                "active_employees": len(active_employees),
                "total_employees": total_employees,
            }

    async def daily_report(self, date_: date | None = None) -> dict:
        """Return a per-day summary.

        Keys: ``date`` (YYYY-MM-DD string), ``created``, ``completed``,
        ``expired``, ``by_priority`` (mapping of priority value to count
        of tasks created that day).
        """
        target_date = date_ or now_local().date()
        start_utc, end_utc = self._day_range(target_date)

        async with self._session_scope() as session:
            created = await self._count_in_range(
                session, Task.created_at, start_utc, end_utc
            )
            completed = await self._count_in_range(
                session, Task.completed_at, start_utc, end_utc
            )
            expired = await self._count_in_range(
                session, Task.expired_at, start_utc, end_utc
            )
            by_priority = await self._count_by_priority_in_range(
                session, Task.created_at, start_utc, end_utc
            )

            return {
                "date": target_date.isoformat(),
                "created": created,
                "completed": completed,
                "expired": expired,
                "by_priority": by_priority,
            }

    async def weekly_report(self, date_: date | None = None) -> dict:
        """Return a per-week summary for the week containing ``date_``.

        Keys: ``week_start``, ``week_end``, ``created``, ``completed``,
        ``expired``, ``by_priority``.
        """
        target_date = date_ or now_local().date()
        monday, sunday = self._week_range(target_date)
        start_utc, _ = self._day_range(monday)
        _, end_utc = self._day_range(sunday)

        async with self._session_scope() as session:
            created = await self._count_in_range(
                session, Task.created_at, start_utc, end_utc
            )
            completed = await self._count_in_range(
                session, Task.completed_at, start_utc, end_utc
            )
            expired = await self._count_in_range(
                session, Task.expired_at, start_utc, end_utc
            )
            by_priority = await self._count_by_priority_in_range(
                session, Task.created_at, start_utc, end_utc
            )

            return {
                "week_start": monday.isoformat(),
                "week_end": sunday.isoformat(),
                "created": created,
                "completed": completed,
                "expired": expired,
                "by_priority": by_priority,
            }

    async def monthly_report(self, date_: date | None = None) -> dict:
        """Return a per-month summary for the month containing ``date_``.

        Keys: ``month_start``, ``month_end``, ``created``, ``completed``,
        ``expired``, ``by_priority``.
        """
        target_date = date_ or now_local().date()
        first, last = self._month_range(target_date)
        start_utc, _ = self._day_range(first)
        _, end_utc = self._day_range(last)

        async with self._session_scope() as session:
            created = await self._count_in_range(
                session, Task.created_at, start_utc, end_utc
            )
            completed = await self._count_in_range(
                session, Task.completed_at, start_utc, end_utc
            )
            expired = await self._count_in_range(
                session, Task.expired_at, start_utc, end_utc
            )
            by_priority = await self._count_by_priority_in_range(
                session, Task.created_at, start_utc, end_utc
            )

            return {
                "month_start": first.isoformat(),
                "month_end": last.isoformat(),
                "created": created,
                "completed": completed,
                "expired": expired,
                "by_priority": by_priority,
            }
