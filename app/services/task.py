"""Task management service — the core domain logic of the bot.

Orchestrates task creation, lifecycle transitions (complete / expire /
archive / restore), queries and filtering. Every state change writes a
:class:`TaskLog` entry (task-centric history) and an :class:`AuditLog`
entry (global, actor-centric audit trail) within the same transaction.

Side-effecting notifications (e.g. "tell the admins the task is done")
are dispatched to :class:`NotificationService` as fire-and-forget calls
— they open their own session and never propagate failures back to the
originating flow.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.models.enums import AuditAction, TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.audit_log import AuditLogRepository
from app.repositories.task import TaskRepository
from app.repositories.task_log import TaskLogRepository
from app.utils.dates import now_utc


class TaskService:
    """Create, transition, query and filter :class:`Task` records."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "TaskService":
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
    # Lifecycle: create / complete / expire / archive / restore
    # ------------------------------------------------------------------ #
    async def create_task(
        self,
        title: str,
        description: str | None,
        employee_id: int,
        priority: TaskPriority,
        deadline: datetime,
        assigned_by: int,
    ) -> Task:
        """Create a new task in :attr:`TaskStatus.PENDING`.

        Also appends a ``created`` task-log entry and a ``TASK_CREATED``
        audit entry.

        Args:
            title: Short task title.
            description: Optional longer description.
            employee_id: Employee the task is assigned to.
            priority: :class:`TaskPriority`.
            deadline: Timezone-aware UTC deadline.
            assigned_by: User id of the assigning admin.

        Returns:
            The newly created :class:`Task`.
        """
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            log_repo = TaskLogRepository(session)
            audit_repo = AuditLogRepository(session)

            task = await task_repo.create(
                {
                    "title": title,
                    "description": description,
                    "employee_id": employee_id,
                    "priority": priority,
                    "deadline": deadline,
                    "assigned_by": assigned_by,
                    "status": TaskStatus.PENDING,
                }
            )

            await log_repo.create(
                {
                    "task_id": task.id,
                    "action": "created",
                    "actor_id": assigned_by,
                    "to_status": TaskStatus.PENDING.value,
                    "message": "Vazifa yaratildi",
                    "occurred_at": now_utc(),
                }
            )

            await audit_repo.create(
                {
                    "action": AuditAction.TASK_CREATED,
                    "actor_id": assigned_by,
                    "target_type": "task",
                    "target_id": task.id,
                    "summary": f"Task #{task.id} created: {task.title}",
                    "detail": {
                        "employee_id": employee_id,
                        "priority": getattr(priority, "value", priority),
                    },
                    "occurred_at": now_utc(),
                }
            )

            logger.info(
                "Created task id={} title={!r} employee={} by={}",
                task.id,
                task.title,
                employee_id,
                assigned_by,
            )
            return task

    async def complete_task(
        self, task_id: int, user_id: int, note: str | None = None
    ) -> tuple[bool, str]:
        """Mark a PENDING task as COMPLETED.

        Args:
            task_id: Primary key of the task.
            user_id: User id of the actor completing the task.
            note: Optional completion note stored on the task.

        Returns:
            ``(success, message)`` — on failure the message is a short
            already-localised Uzbek reason.
        """
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            log_repo = TaskLogRepository(session)
            audit_repo = AuditLogRepository(session)

            task = await task_repo.get_with_relations(task_id)
            if task is None:
                return (False, "Vazifa topilmadi.")

            if task.status != TaskStatus.PENDING:
                return (
                    False,
                    "Vazifa allaqachon yakunlangan.",
                )

            from_status = task.status
            task.status = TaskStatus.COMPLETED
            task.completed_at = now_utc()
            task.completion_note = note
            await task_repo.save(task)

            await log_repo.create(
                {
                    "task_id": task.id,
                    "action": "completed",
                    "actor_id": user_id,
                    "from_status": getattr(from_status, "value", str(from_status)),
                    "to_status": TaskStatus.COMPLETED.value,
                    "message": note or "Vazifa bajarildi",
                    "occurred_at": now_utc(),
                }
            )

            await audit_repo.create(
                {
                    "action": AuditAction.TASK_COMPLETED,
                    "actor_id": user_id,
                    "target_type": "task",
                    "target_id": task.id,
                    "summary": f"Task #{task.id} completed",
                    "detail": {"note": note},
                    "occurred_at": now_utc(),
                }
            )

            logger.info(
                "Completed task id={} by user={}", task.id, user_id
            )

        # Fire-and-forget admin notification — never let a notification
        # failure roll back the completion transaction above.
        try:
            from app.services.notification import NotificationService

            await NotificationService().send_task_completed_to_admin(
                task_id
            )
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning(
                "Failed to dispatch task-completed notification for "
                "task {}: {}",
                task_id,
                exc,
            )

        return (True, "Vazifa muvaffaqiyatli yakunlandi.")

    async def expire_task(self, task_id: int) -> None:
        """Transition a task to :attr:`TaskStatus.EXPIRED`.

        Used by the scheduler when a task's deadline passes without
        completion.
        """
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            log_repo = TaskLogRepository(session)
            audit_repo = AuditLogRepository(session)

            task = await task_repo.get_by_id(task_id)
            if task is None:
                logger.warning("expire_task: task {} not found", task_id)
                return

            from_status = task.status
            task.status = TaskStatus.EXPIRED
            task.expired_at = now_utc()
            await task_repo.save(task)

            await log_repo.create(
                {
                    "task_id": task.id,
                    "action": "expired",
                    "from_status": getattr(from_status, "value", str(from_status)),
                    "to_status": TaskStatus.EXPIRED.value,
                    "message": "Vazifa muddati o'tdi",
                    "occurred_at": now_utc(),
                }
            )

            await audit_repo.create(
                {
                    "action": AuditAction.TASK_EXPIRED,
                    "target_type": "task",
                    "target_id": task.id,
                    "summary": f"Task #{task.id} expired",
                    "occurred_at": now_utc(),
                }
            )

            logger.info("Expired task id={}", task_id)

    async def archive_task(self, task_id: int) -> None:
        """Transition a task to :attr:`TaskStatus.ARCHIVED`."""
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            log_repo = TaskLogRepository(session)
            audit_repo = AuditLogRepository(session)

            task = await task_repo.get_by_id(task_id)
            if task is None:
                logger.warning("archive_task: task {} not found", task_id)
                return

            from_status = task.status
            task.status = TaskStatus.ARCHIVED
            task.archived_at = now_utc()
            await task_repo.save(task)

            await log_repo.create(
                {
                    "task_id": task.id,
                    "action": "archived",
                    "from_status": getattr(from_status, "value", str(from_status)),
                    "to_status": TaskStatus.ARCHIVED.value,
                    "message": "Vazifa arxivlandi",
                    "occurred_at": now_utc(),
                }
            )

            await audit_repo.create(
                {
                    "action": AuditAction.TASK_ARCHIVED,
                    "target_type": "task",
                    "target_id": task.id,
                    "summary": f"Task #{task.id} archived",
                    "occurred_at": now_utc(),
                }
            )

            logger.info("Archived task id={}", task_id)

    async def restore_task(self, task_id: int) -> None:
        """Restore an archived task back to :attr:`TaskStatus.PENDING`."""
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            log_repo = TaskLogRepository(session)
            audit_repo = AuditLogRepository(session)

            task = await task_repo.get_by_id(task_id)
            if task is None:
                logger.warning("restore_task: task {} not found", task_id)
                return

            from_status = task.status
            task.status = TaskStatus.PENDING
            task.archived_at = None
            await task_repo.save(task)

            await log_repo.create(
                {
                    "task_id": task.id,
                    "action": "restored",
                    "from_status": getattr(from_status, "value", str(from_status)),
                    "to_status": TaskStatus.PENDING.value,
                    "message": "Vazifa arxivdan qaytarildi",
                    "occurred_at": now_utc(),
                }
            )

            await audit_repo.create(
                {
                    "action": AuditAction.TASK_RESTORED,
                    "target_type": "task",
                    "target_id": task.id,
                    "summary": f"Task #{task.id} restored",
                    "occurred_at": now_utc(),
                }
            )

            logger.info("Restored task id={}", task_id)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    async def get_task(self, task_id: int) -> Task | None:
        """Return the task with relations eagerly loaded, or ``None``."""
        async with self._session_scope() as session:
            repo = TaskRepository(session)
            return await repo.get_with_relations(task_id)

    async def get_employee_tasks(
        self, employee_id: int, status: TaskStatus | None = None
    ) -> list[Task]:
        """Return tasks for an employee, optionally filtered by status."""
        async with self._session_scope() as session:
            repo = TaskRepository(session)
            return await repo.get_by_employee(employee_id, status)

    async def get_today_tasks(self, employee_id: int) -> list[Task]:
        """Return tasks for an employee whose deadline falls on today."""
        async with self._session_scope() as session:
            repo = TaskRepository(session)
            return await repo.get_today_tasks(employee_id)

    async def get_pending_tasks(self) -> list[Task]:
        """Return all PENDING tasks (used by the scheduler)."""
        async with self._session_scope() as session:
            repo = TaskRepository(session)
            return await repo.get_pending_tasks()

    async def get_tasks_expiring_before(
        self, deadline: datetime
    ) -> list[Task]:
        """Return PENDING tasks whose deadline is strictly before ``deadline``.

        Used by the scheduler to find tasks that should be expired.
        """
        async with self._session_scope() as session:
            repo = TaskRepository(session)
            return await repo.get_pending_before(deadline)

    async def search_tasks(
        self,
        query: str,
        employee_id: int | None = None,
        status: TaskStatus | None = None,
        limit: int = 50,
    ) -> list[Task]:
        """Search tasks by case-insensitive substring in title/description."""
        async with self._session_scope() as session:
            repo = TaskRepository(session)
            return await repo.search(query, employee_id, status, limit)

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

        ``date_from`` / ``date_to`` filter on the deadline column.
        """
        async with self._session_scope() as session:
            repo = TaskRepository(session)
            return await repo.get_all_filtered(
                employee_id=employee_id,
                status=status,
                priority=priority,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset,
            )

    # ------------------------------------------------------------------ #
    # Task log
    # ------------------------------------------------------------------ #
    async def add_task_log(
        self,
        task_id: int,
        action: str,
        actor_id: int | None = None,
        from_status: str | None = None,
        to_status: str | None = None,
        message: str | None = None,
    ) -> None:
        """Append a single :class:`TaskLog` entry for a task.

        This is a low-level helper — the lifecycle methods above already
        log their own transitions. Use this only for custom events.
        """
        async with self._session_scope() as session:
            log_repo = TaskLogRepository(session)
            await log_repo.create(
                {
                    "task_id": task_id,
                    "action": action,
                    "actor_id": actor_id,
                    "from_status": from_status,
                    "to_status": to_status,
                    "message": message,
                    "occurred_at": now_utc(),
                }
            )
