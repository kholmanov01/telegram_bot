"""APScheduler wiring — registers jobs and manages the scheduler lifecycle.

A single :class:`TaskScheduler` instance is exposed as the module-level
:data:`scheduler` singleton. The bot's main entry point should::

    from app.scheduler import scheduler, register_scheduler

    register_scheduler()      # registers the three jobs on the singleton
    await scheduler.start()   # after starting polling (or before)
    ...
    await scheduler.shutdown()

The scheduler runs on the same asyncio event loop as aiogram. The job
coroutines in :mod:`app.scheduler.jobs` open their own DB sessions via
the service layer, so the scheduler itself never manages sessions.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.config.settings import settings
from app.scheduler.jobs import (
    check_expired_tasks,
    daily_summary_report,
    send_task_reminders,
)


class TaskScheduler:
    """Owns an :class:`AsyncIOScheduler` and the job registration table.

    The scheduler is created lazily in :meth:`__init__` (no I/O, no
    threads) and is only actually started when :meth:`start` is awaited.
    """

    def __init__(self) -> None:
        """Create a scheduler bound to ``settings.scheduler_timezone``."""
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler(
            timezone=settings.scheduler_timezone,
        )
        # APScheduler's AsyncIOScheduler.shutdown() defers the actual
        # state transition to the event loop, so ``scheduler.running``
        # may stay True for one tick after a shutdown request. We track
        # our own flag to make repeated shutdown() calls a clean no-op
        # instead of letting APScheduler raise ``SchedulerNotRunningError``
        # from a deferred callback.
        self._shutdown_requested: bool = False

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def setup(self) -> None:
        """Register all scheduled jobs on the underlying scheduler.

        ``replace_existing=True`` makes the call idempotent: re-invoking
        :meth:`setup` simply updates the triggers / job references
        instead of raising a ``ConflictingIdError``.

        Registered jobs (all async coroutines):

        ==================  ==================================  ==============
        Job id              Coroutine                           Schedule
        ==================  ==================================  ==============
        ``check_expired``   :func:`check_expired_tasks`         every minute
        ``reminders``       :func:`send_task_reminders`         every minute
        ``daily_summary``   :func:`daily_summary_report`        18:05 daily
        ==================  ==================================  ==============
        """
        # Every minute: expire tasks whose deadline has passed.
        self.scheduler.add_job(
            check_expired_tasks,
            trigger=CronTrigger(minute="*"),
            id="check_expired",
            replace_existing=True,
        )

        # Every minute: dispatch pre-deadline reminders.
        self.scheduler.add_job(
            send_task_reminders,
            trigger=IntervalTrigger(minutes=1),
            id="reminders",
            replace_existing=True,
        )

        # 18:05 in scheduler_timezone: daily summary to super admins.
        self.scheduler.add_job(
            daily_summary_report,
            trigger=CronTrigger(hour=18, minute=5),
            id="daily_summary",
            replace_existing=True,
        )

        logger.info(
            "Scheduler setup complete — {} jobs registered "
            "(tz={})",
            len(self.scheduler.get_jobs()),
            settings.scheduler_timezone,
        )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self) -> None:
        """Start the scheduler.

        ``AsyncIOScheduler.start`` is synchronous — it only schedules
        the scheduler onto the running event loop. The ``async``
        signature keeps the caller's startup sequence uniform
        (``await scheduler.start()``) and clearly signals that it must
        be called from within a running loop.

        No-op (with a warning) if the scheduler is already running.
        Resets the internal shutdown-requested flag so a previously
        shut-down scheduler instance can be started again.
        """
        if self.scheduler.running:
            logger.warning(
                "Scheduler is already running — start() ignored"
            )
            return
        self._shutdown_requested = False
        self.scheduler.start()
        logger.info(
            "Scheduler started (tz={})", settings.scheduler_timezone
        )

    async def shutdown(self) -> None:
        """Shut the scheduler down without waiting for in-flight jobs.

        ``wait=False`` ensures a fast, deterministic shutdown during
        application teardown. No-op (with a warning) if the scheduler is
        not running, or if a shutdown has already been requested but
        APScheduler's deferred state transition has not yet run.
        """
        if self._shutdown_requested:
            logger.warning(
                "Shutdown already requested — shutdown() ignored"
            )
            return
        if not self.scheduler.running:
            logger.warning(
                "Scheduler is not running — shutdown() ignored"
            )
            return
        self._shutdown_requested = True
        try:
            self.scheduler.shutdown(wait=False)
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning(
                "Scheduler shutdown raised: {}", exc
            )
            return
        logger.info("Scheduler shut down")


# Module-level singleton imported by the bot's main entry point.
scheduler: TaskScheduler = TaskScheduler()
