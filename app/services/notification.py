"""Notification service — dispatches Telegram messages and records them.

Every notification sent to a user (employee or admin) flows through this
service. For each message:

1. The message is sent via the :data:`bot` instance (Aiogram).
2. A :class:`Notification` row records the outcome (``SENT`` or
   ``FAILED``) along with the message body, error string and timestamp.
3. On success a ``NOTIFICATION_SENT`` audit entry is appended.

All Telegram errors are caught — a notification failure NEVER propagates
to the caller. This is critical because notifications are often
fire-and-forget side effects of task transitions.

The :meth:`_send_and_record` helper DRYs up the send + record + audit
logic. It accepts the caller's session so that, where atomicity matters
(e.g. :meth:`send_reminder` idempotency), everything happens in one
transaction.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from aiogram.exceptions import TelegramAPIError
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.instance import bot
from app.bot.keyboards.common import task_card_inline
from app.database.session import get_session
from app.models.enums import (
    AuditAction,
    NotificationStatus,
    NotificationType,
    TaskStatus,
    UserRole,
)
from app.models.notification import Notification
from app.notifications.templates import (
    deadline_passed_admin,
    deadline_passed_employee,
    new_task_notification,
    reminder_notification,
    task_completed_admin,
)
from app.repositories.audit_log import AuditLogRepository
from app.repositories.notification import NotificationRepository
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.utils.dates import format_datetime, now_utc


class NotificationService:
    """Send Telegram notifications and persist their delivery status."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "NotificationService":
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
    # Core send + record helper
    # ------------------------------------------------------------------ #
    async def _send_and_record(
        self,
        session: AsyncSession,
        telegram_id: int,
        text: str,
        task_id: int | None,
        ntype: NotificationType,
        user_id: int | None = None,
        offset: int | None = None,
        reply_markup: Any = None,
    ) -> Notification:
        """Send a Telegram message and record the outcome.

        Uses ``session`` for all DB writes so that the notification row
        and audit entry share the caller's transaction. Never raises —
        every Telegram error is caught and stored as a ``FAILED``
        notification.

        Args:
            session: Open :class:`AsyncSession`.
            telegram_id: Recipient Telegram id.
            text: HTML message body.
            task_id: Related task id (if any).
            ntype: :class:`NotificationType`.
            user_id: Recipient user id (if known).
            offset: Reminder offset in minutes (for ``REMINDER`` type).
            reply_markup: Optional inline keyboard.

        Returns:
            The persisted :class:`Notification` row.
        """
        notif_repo = NotificationRepository(session)
        audit_repo = AuditLogRepository(session)

        sent = False
        error_str: str | None = None
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=text,
                reply_markup=reply_markup,
            )
            sent = True
            logger.info(
                "Sent {} notification to telegram_id={}",
                ntype.value,
                telegram_id,
            )
        except TelegramAPIError as exc:
            error_str = str(exc)[:500]
            logger.warning(
                "Telegram API error sending {} to {}: {}",
                ntype.value,
                telegram_id,
                exc,
            )
        except Exception as exc:  # noqa: BLE001 — defensive catch-all
            error_str = str(exc)[:500]
            logger.error(
                "Unexpected error sending {} to {}: {}",
                ntype.value,
                telegram_id,
                exc,
            )

        notification = await notif_repo.create(
            {
                "type": ntype,
                "status": (
                    NotificationStatus.SENT
                    if sent
                    else NotificationStatus.FAILED
                ),
                "user_id": user_id,
                "recipient_telegram_id": telegram_id,
                "task_id": task_id,
                "reminder_offset_minutes": offset,
                "body": text,
                "error": error_str,
                "sent_at": now_utc(),
            }
        )

        if sent:
            await audit_repo.create(
                {
                    "action": AuditAction.NOTIFICATION_SENT,
                    "target_type": "notification",
                    "target_id": notification.id,
                    "summary": (
                        f"Sent {ntype.value} notification "
                        f"to {telegram_id}"
                    ),
                    "detail": {
                        "task_id": task_id,
                        "offset": offset,
                    },
                    "occurred_at": now_utc(),
                }
            )

        return notification

    # ------------------------------------------------------------------ #
    # Admin discovery
    # ------------------------------------------------------------------ #
    async def _get_super_admins(
        self, session: AsyncSession
    ) -> list:
        """Return all active super-admin users."""
        user_repo = UserRepository(session)
        return await user_repo.find_many(
            limit=500,
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def send_new_task_notification(self, task_id: int) -> None:
        """Notify the assigned employee that a new task was created.

        If the employee has no linked user or the user has no
        ``telegram_id``, a ``FAILED`` notification is recorded and the
        method returns without raising.

        After sending the task card message, every attachment linked to
        the task is re-sent to the employee via
        :meth:`AttachmentService.send_attachments_to_user`. Attachment
        dispatch failures are logged and never propagated.
        """
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.get_with_relations(task_id)
            if task is None:
                logger.warning(
                    "send_new_task_notification: task {} not found",
                    task_id,
                )
                return

            employee = task.employee
            user = employee.user if employee is not None else None
            if user is None or user.telegram_id is None:
                # Record the failure so admins can see the gap.
                notif_repo = NotificationRepository(session)
                await notif_repo.create(
                    {
                        "type": NotificationType.NEW_TASK,
                        "status": NotificationStatus.FAILED,
                        "user_id": user.id if user is not None else None,
                        "recipient_telegram_id": (
                            user.telegram_id
                            if user is not None
                            else None
                        ),
                        "task_id": task_id,
                        "body": None,
                        "error": (
                            "Employee has no linked Telegram user"
                        ),
                        "sent_at": now_utc(),
                    }
                )
                logger.warning(
                    "Cannot send NEW_TASK notification for task {}: "
                    "no telegram_id",
                    task_id,
                )
                return

            # Resolve the attachment count for the card line (avoid lazy
            # loading ``task.attachments`` since ``get_with_relations``
            # does not eager-load it).
            try:
                from app.services.attachment import AttachmentService

                attachment_count = await AttachmentService.with_session(
                    session
                ).get_attachment_count(task_id)
            except Exception as exc:  # noqa: BLE001 — defensive
                logger.warning(
                    "Could not count attachments for task {}: {}",
                    task_id,
                    exc,
                )
                attachment_count = 0

            text = new_task_notification(task, attachment_count=attachment_count)
            markup = task_card_inline(
                task.id,
                viewer_is_employee=True,
                attachment_count=attachment_count,
            )
            await self._send_and_record(
                session,
                user.telegram_id,
                text,
                task_id,
                NotificationType.NEW_TASK,
                user_id=user.id,
                reply_markup=markup,
            )

        # After the card message has been sent (or attempted), re-send
        # every attachment to the employee. This runs in its own session
        # so a failure here does not affect the notification record above.
        try:
            from app.services.attachment import AttachmentService

            await AttachmentService().send_attachments_to_user(
                task_id, user.telegram_id
            )
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning(
                "Failed to send attachments of task {} to {}: {}",
                task_id,
                user.telegram_id,
                exc,
            )

    async def send_reminder(
        self, task_id: int, offset_minutes: int
    ) -> None:
        """Send a pre-deadline reminder to the assigned employee.

        Idempotent: if ``offset_minutes`` is already recorded in
        ``task.sent_reminders`` the call is a no-op. The idempotency
        check, message send, notification record and ``sent_reminders``
        update all happen in one transaction.
        """
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.get_with_relations(task_id)
            if task is None:
                logger.warning(
                    "send_reminder: task {} not found", task_id
                )
                return

            # Only remind tasks still awaiting completion.
            if task.status != TaskStatus.PENDING:
                return

            # Idempotency: parse the comma-separated sent_reminders set.
            sent_list = [
                s.strip()
                for s in (task.sent_reminders or "").split(",")
                if s.strip()
            ]
            if str(offset_minutes) in sent_list:
                logger.debug(
                    "Reminder {}min for task {} already sent — skipping",
                    offset_minutes,
                    task_id,
                )
                return

            employee = task.employee
            user = employee.user if employee is not None else None
            if user is None or user.telegram_id is None:
                logger.warning(
                    "Cannot send reminder for task {}: no telegram_id",
                    task_id,
                )
                return

            text = reminder_notification(task, offset_minutes)
            markup = task_card_inline(
                task.id, viewer_is_employee=True
            )
            notification = await self._send_and_record(
                session,
                user.telegram_id,
                text,
                task_id,
                NotificationType.REMINDER,
                user_id=user.id,
                offset=offset_minutes,
                reply_markup=markup,
            )

            # Only stamp sent_reminders when the message actually went out.
            if notification.status == NotificationStatus.SENT:
                sent_list.append(str(offset_minutes))
                task.sent_reminders = ",".join(sent_list)
                await task_repo.save(task)

    async def send_deadline_passed(self, task_id: int) -> None:
        """Notify both the employee and all admins that a deadline passed.

        The employee receives :func:`deadline_passed_employee`; each
        active super admin receives :func:`deadline_passed_admin`.
        """
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.get_with_relations(task_id)
            if task is None:
                logger.warning(
                    "send_deadline_passed: task {} not found", task_id
                )
                return

            employee = task.employee
            user = employee.user if employee is not None else None

            # 1. Employee notification.
            if user is not None and user.telegram_id is not None:
                text = deadline_passed_employee(task)
                markup = task_card_inline(
                    task.id, viewer_is_employee=True
                )
                await self._send_and_record(
                    session,
                    user.telegram_id,
                    text,
                    task_id,
                    NotificationType.DEADLINE_PASSED,
                    user_id=user.id,
                    reply_markup=markup,
                )

            # 2. Admin notifications.
            employee_name = (
                employee.full_name if employee is not None else "—"
            )
            admin_text = deadline_passed_admin(
                employee_name, task.title
            )
            admins = await self._get_super_admins(session)
            for admin in admins:
                if admin.telegram_id is None:
                    continue
                await self._send_and_record(
                    session,
                    admin.telegram_id,
                    admin_text,
                    task_id,
                    NotificationType.DEADLINE_PASSED,
                    user_id=admin.id,
                )

    async def send_task_completed_to_admin(
        self, task_id: int
    ) -> None:
        """Notify all super admins that an employee completed a task."""
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.get_with_relations(task_id)
            if task is None:
                logger.warning(
                    "send_task_completed_to_admin: task {} not found",
                    task_id,
                )
                return

            employee = task.employee
            employee_name = (
                employee.full_name if employee is not None else "—"
            )
            completed_at_str = format_datetime(task.completed_at)

            text = task_completed_admin(
                employee_name, task.title, completed_at_str
            )
            admins = await self._get_super_admins(session)
            for admin in admins:
                if admin.telegram_id is None:
                    continue
                await self._send_and_record(
                    session,
                    admin.telegram_id,
                    text,
                    task_id,
                    NotificationType.TASK_COMPLETED,
                    user_id=admin.id,
                )

    async def send_task_expired_to_admin(
        self, task_id: int
    ) -> None:
        """Notify all super admins that a task has expired."""
        async with self._session_scope() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.get_with_relations(task_id)
            if task is None:
                logger.warning(
                    "send_task_expired_to_admin: task {} not found",
                    task_id,
                )
                return

            employee = task.employee
            employee_name = (
                employee.full_name if employee is not None else "—"
            )

            text = deadline_passed_admin(employee_name, task.title)
            admins = await self._get_super_admins(session)
            for admin in admins:
                if admin.telegram_id is None:
                    continue
                await self._send_and_record(
                    session,
                    admin.telegram_id,
                    text,
                    task_id,
                    NotificationType.TASK_EXPIRED,
                    user_id=admin.id,
                )
