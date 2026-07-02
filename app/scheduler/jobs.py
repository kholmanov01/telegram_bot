"""Scheduled job functions for the task management bot.

These coroutines are registered with the APScheduler
:class:`AsyncIOScheduler` and executed on the same event loop as
aiogram. They orchestrate the background work of the bot:

* :func:`check_expired_tasks` — every minute, expire PENDING tasks whose
  deadline has passed and notify the employee + admins.
* :func:`send_task_reminders` — every minute, dispatch pre-deadline
  reminders at well-defined offsets (idempotent — see
  :meth:`NotificationService.send_reminder`).
* :func:`daily_summary_report` — once a day at 18:05 in
  ``settings.scheduler_timezone``, compute a daily report and send a
  short summary to every active super admin.

Each job is defensive: per-task failures are caught and logged so one
bad row never stops the whole loop. Jobs never re-raise — APScheduler
would log it but we keep control of the log format and severity.

The jobs call services that open their own DB sessions, so they do NOT
manage sessions themselves (exception: :func:`daily_summary_report`
opens a one-shot session for the admin lookup as instructed).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.bot.instance import bot
from app.database.session import get_session
from app.models.enums import UserRole
from app.repositories.user import UserRepository
from app.services import (
    NotificationService,
    StatisticsService,
    TaskService,
)
from app.utils.dates import now_utc

# Reminder offsets (minutes *before* the deadline) at which an employee
# should be reminded. The order matters only for log readability — see
# :func:`send_task_reminders` for the actual matching logic.
REMINDER_OFFSETS_MINUTES: tuple[int, ...] = (1440, 720, 360, 60, 30, 10)

# Half-window (minutes) used to detect which offset(s) a task currently
# matches. With a 1-minute scheduler tick and a 1-minute tolerance, each
# pending task is considered for each offset during the minute in which
# ``minutes_left`` falls within ``[offset-1, offset+1]``.
REMINDER_TOLERANCE_MINUTES: int = 1


async def check_expired_tasks() -> None:
    """Expire PENDING tasks whose deadline has passed.

    Workflow per task:

    1. Transition the task to :attr:`TaskStatus.EXPIRED` via
       :meth:`TaskService.expire_task`.
    2. Notify the assigned employee via
       :meth:`NotificationService.send_deadline_passed`.
    3. Notify all super admins via
       :meth:`NotificationService.send_task_expired_to_admin`.

    The expire transition is independent of the notifications: if a
    notification raises, the task has already been expired and the loop
    continues with the next task.
    """
    logger.info("Scheduled job: check_expired_tasks — starting pass")
    now = now_utc()
    expired_count = 0

    try:
        tasks = await TaskService().get_tasks_expiring_before(now)
    except Exception as exc:  # noqa: BLE001 — defensive catch-all
        logger.exception(
            "Failed to fetch tasks expiring before {}: {}", now, exc
        )
        return

    for task in tasks:
        task_id: int | None = getattr(task, "id", None)
        if task_id is None:
            logger.warning("Skipping task without id: {!r}", task)
            continue

        # 1. Transition the task to EXPIRED.
        try:
            await TaskService().expire_task(task_id)
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.exception(
                "Failed to expire task id={}: {}", task_id, exc
            )
            continue

        # 2. Notify the employee that the deadline has passed.
        try:
            await NotificationService().send_deadline_passed(task_id)
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.exception(
                "Failed to send deadline_passed notification for "
                "task id={}: {}",
                task_id,
                exc,
            )

        # 3. Notify all super admins that the task expired.
        try:
            await NotificationService().send_task_expired_to_admin(task_id)
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.exception(
                "Failed to send task_expired_to_admin notification for "
                "task id={}: {}",
                task_id,
                exc,
            )

        expired_count += 1

    logger.info("Expired {} tasks", expired_count)


async def send_task_reminders() -> None:
    """Send pre-deadline reminders to employees.

    For every PENDING task we compute the number of minutes left until
    the deadline. For each configured reminder offset, if
    ``abs(minutes_left - offset) <= REMINDER_TOLERANCE_MINUTES`` the
    reminder is dispatched via
    :meth:`NotificationService.send_reminder`.

    :meth:`NotificationService.send_reminder` is idempotent (it checks
    ``task.sent_reminders``), so re-calling within the one-minute window
    is safe and a duplicate run will simply no-op.
    """
    logger.info("Scheduled job: send_task_reminders — starting pass")
    now = now_utc()
    reminders_dispatched = 0

    try:
        pending_tasks = await TaskService().get_pending_tasks()
    except Exception as exc:  # noqa: BLE001 — defensive catch-all
        logger.exception("Failed to fetch pending tasks: {}", exc)
        return

    for task in pending_tasks:
        task_id: int | None = getattr(task, "id", None)
        deadline: datetime | None = getattr(task, "deadline", None)
        if task_id is None or deadline is None:
            logger.warning(
                "Skipping task without id/deadline: id={!r} deadline={!r}",
                task_id,
                deadline,
            )
            continue

        # Normalise naive datetimes to tz-aware UTC for safe subtraction.
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        minutes_left = (deadline - now).total_seconds() / 60.0

        for offset in REMINDER_OFFSETS_MINUTES:
            if abs(minutes_left - offset) > REMINDER_TOLERANCE_MINUTES:
                continue
            try:
                await NotificationService().send_reminder(task_id, offset)
                reminders_dispatched += 1
            except Exception as exc:  # noqa: BLE001 — defensive
                logger.exception(
                    "Failed to send reminder (offset={}min) for "
                    "task id={}: {}",
                    offset,
                    task_id,
                    exc,
                )

    logger.info(
        "Dispatched {} reminder notifications", reminders_dispatched
    )


async def daily_summary_report() -> None:
    """Compute a daily report and send a short summary to super admins.

    Runs at 18:05 in ``settings.scheduler_timezone``. The full report
    dict is logged; a compact HTML summary is delivered to every active
    super admin via :func:`bot.send_message`. Per-admin delivery
    failures are caught and logged so one blocked chat never stops the
    others.
    """
    logger.info("Scheduled job: daily_summary_report — starting")

    # 1. Compute the daily report.
    try:
        report = await StatisticsService().daily_report()
    except Exception as exc:  # noqa: BLE001 — defensive catch-all
        logger.exception("Failed to compute daily report: {}", exc)
        return

    logger.info("Daily report: {}", _serialise_report(report))

    summary_text = _format_daily_summary(report)
    if not summary_text:
        logger.warning(
            "Daily summary text is empty — skipping admin dispatch"
        )
        return

    # 2. Find every active super admin.
    try:
        async with get_session() as session:
            repo = UserRepository(session)
            admins = await repo.find_many(
                limit=500,
                role=UserRole.SUPER_ADMIN,
                is_active=True,
            )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.exception(
            "Failed to fetch super admins for daily summary: {}", exc
        )
        return

    # 3. Deliver the summary to each admin.
    sent_count = 0
    for admin in admins:
        telegram_id: int | None = getattr(admin, "telegram_id", None)
        if not telegram_id:
            continue
        try:
            await bot.send_message(
                chat_id=telegram_id, text=summary_text
            )
            sent_count += 1
            logger.info(
                "Sent daily summary to admin telegram_id={}", telegram_id
            )
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning(
                "Failed to send daily summary to admin "
                "telegram_id={}: {}",
                telegram_id,
                exc,
            )

    logger.info(
        "Daily summary delivered to {} of {} active super admins",
        sent_count,
        len(admins),
    )


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #
def _serialise_report(report: dict[str, Any]) -> str:
    """Return a compact JSON string of the daily report for log lines.

    Falls back to ``str(report)`` if JSON serialisation fails for any
    reason (it never re-raises from a logger call site).
    """
    try:
        return json.dumps(report, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001 — defensive
        return str(report)


def _format_daily_summary(report: dict[str, Any]) -> str:
    """Format the daily report dict as a short HTML Telegram message.

    All interpolated values are integers or short enum/date strings
    produced by the service, so no HTML escaping is necessary.
    """
    date_str = str(report.get("date", "") or "")
    created = report.get("created", 0)
    completed = report.get("completed", 0)
    expired = report.get("expired", 0)
    by_priority = report.get("by_priority", {}) or {}

    priority_lines = "\n".join(
        f"  • {priority}: {count}"
        for priority, count in by_priority.items()
    )
    if not priority_lines:
        priority_lines = "  • —"

    return (
        "📊 <b>Kunlik hisobot</b>\n"
        f"Sana: <b>{date_str}</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🆕 Yaratildi: <b>{created}</b>\n"
        f"✅ Bajarildi: <b>{completed}</b>\n"
        f"❌ Muddati o'tdi: <b>{expired}</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<i>Ustuvorlik bo'yicha:</i>\n{priority_lines}"
    )
