"""Repository for the :class:`Task` aggregate."""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytz
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import settings
from app.models.employee import Employee
from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Data-access layer for :class:`Task` records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a session and the Task model."""
        super().__init__(session, Task)

    async def get_with_relations(self, task_id: int) -> Task | None:
        """Return the task by id with employee, employee.user and assigner loaded.

        Args:
            task_id: Primary key of the task.

        Returns:
            The :class:`Task` with relations eagerly loaded, or ``None``.
        """
        stmt = (
            select(Task)
            .options(
                selectinload(Task.employee).selectinload(Employee.user),
                selectinload(Task.assigner),
            )
            .where(Task.id == task_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_pending_tasks(self) -> list[Task]:
        """Return all tasks currently in :attr:`TaskStatus.PENDING`."""
        stmt = (
            select(Task)
            .where(Task.status == TaskStatus.PENDING)
            .order_by(Task.deadline.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_before(self, deadline: datetime) -> list[Task]:
        """Return PENDING tasks whose deadline is strictly before ``deadline``.

        Args:
            deadline: Upper bound (exclusive) for the task deadline.

        Returns:
            List of matching tasks ordered by deadline ascending.
        """
        stmt = (
            select(Task)
            .where(
                Task.status == TaskStatus.PENDING,
                Task.deadline < deadline,
            )
            .order_by(Task.deadline.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_employee(
        self, employee_id: int, status: TaskStatus | None = None
    ) -> list[Task]:
        """Return tasks assigned to the given employee, optionally filtered by status.

        Args:
            employee_id: Employee primary key.
            status: Optional status filter.

        Returns:
            List of matching tasks ordered by deadline ascending.
        """
        stmt = select(Task).where(Task.employee_id == employee_id)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.deadline.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_today_tasks(self, employee_id: int) -> list[Task]:
        """Return tasks for the employee whose deadline falls within today.

        "Today" is determined in :attr:`settings.app_timezone`. The deadline
        column is stored as timezone-aware UTC, so the day boundaries are
        computed in the application timezone and then converted to UTC for
        the comparison.

        Args:
            employee_id: Employee primary key.

        Returns:
            List of tasks whose deadline is within the current calendar day.
        """
        app_tz = pytz.timezone(settings.app_timezone)
        now_in_app_tz = datetime.now(app_tz)
        today = now_in_app_tz.date()

        start_of_day = app_tz.localize(datetime.combine(today, time.min))
        end_of_day = app_tz.localize(datetime.combine(today, time.max))

        start_utc = start_of_day.astimezone(timezone.utc)
        end_utc = end_of_day.astimezone(timezone.utc)

        stmt = (
            select(Task)
            .where(
                Task.employee_id == employee_id,
                Task.deadline >= start_utc,
                Task.deadline <= end_utc,
            )
            .order_by(Task.deadline.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_completed_tasks(self, employee_id: int) -> list[Task]:
        """Return completed tasks for the given employee ordered by completion time desc.

        Args:
            employee_id: Employee primary key.

        Returns:
            List of completed tasks.
        """
        stmt = (
            select(Task)
            .where(
                Task.employee_id == employee_id,
                Task.status == TaskStatus.COMPLETED,
            )
            .order_by(Task.completed_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        query: str,
        employee_id: int | None = None,
        status: TaskStatus | None = None,
        limit: int = 50,
    ) -> list[Task]:
        """Search tasks by case-insensitive substring in title or description.

        Args:
            query: Search substring.
            employee_id: Optional employee filter.
            status: Optional status filter.
            limit: Maximum number of results.

        Returns:
            List of matching tasks ordered by id descending.
        """
        pattern = f"%{query}%"
        stmt = select(Task).where(
            or_(
                Task.title.ilike(pattern),
                Task.description.ilike(pattern),
            )
        )
        if employee_id is not None:
            stmt = stmt.where(Task.employee_id == employee_id)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.id.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(
        self, employee_id: int | None = None
    ) -> dict[TaskStatus, int]:
        """Return a count of tasks grouped by status.

        All four statuses are always present in the returned dict, even if
        their count is zero.

        Args:
            employee_id: Optional employee filter.

        Returns:
            Mapping of :class:`TaskStatus` to integer count.
        """
        stmt = select(Task.status, func.count()).group_by(Task.status)
        if employee_id is not None:
            stmt = stmt.where(Task.employee_id == employee_id)
        result = await self.session.execute(stmt)

        counts: dict[TaskStatus, int] = {status: 0 for status in TaskStatus}
        for status, count in result.all():
            if status in counts:
                counts[status] = int(count)
        return counts

    async def get_all_filtered(
        self,
        employee_id: int | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        """Return tasks matching the provided filter combination.

        ``date_from`` / ``date_to`` filter on the task deadline column.

        Args:
            employee_id: Optional employee filter.
            status: Optional status filter.
            priority: Optional priority filter.
            date_from: Optional inclusive lower bound for the deadline.
            date_to: Optional inclusive upper bound for the deadline.
            limit: Page size.
            offset: Page offset.

        Returns:
            List of matching tasks ordered by deadline descending.
        """
        stmt = select(Task)
        if employee_id is not None:
            stmt = stmt.where(Task.employee_id == employee_id)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        if date_from is not None:
            stmt = stmt.where(Task.deadline >= date_from)
        if date_to is not None:
            stmt = stmt.where(Task.deadline <= date_to)
        stmt = stmt.order_by(Task.deadline.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_completion_times(
        self,
        employee_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[tuple[Task, float]]:
        """Return completed tasks paired with their completion time in seconds.

        The completion time is computed as
        ``(completed_at - created_at).total_seconds()``. Filters on
        ``completed_at`` are applied when ``date_from`` / ``date_to`` are
        provided.

        Args:
            employee_id: Optional employee filter.
            date_from: Optional inclusive lower bound for ``completed_at``.
            date_to: Optional inclusive upper bound for ``completed_at``.

        Returns:
            List of ``(task, seconds_float)`` tuples.
        """
        stmt = select(Task).where(
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at.is_not(None),
        )
        if employee_id is not None:
            stmt = stmt.where(Task.employee_id == employee_id)
        if date_from is not None:
            stmt = stmt.where(Task.completed_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Task.completed_at <= date_to)
        result = await self.session.execute(stmt)
        tasks = list(result.scalars().all())

        completion_times: list[tuple[Task, float]] = []
        for task in tasks:
            if task.completed_at is None or task.created_at is None:
                continue
            seconds = (task.completed_at - task.created_at).total_seconds()
            completion_times.append((task, float(seconds)))
        return completion_times
