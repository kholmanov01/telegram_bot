"""Scheduler package — APScheduler wiring for the task management bot.

Exposes:

* :class:`TaskScheduler` — owns the :class:`AsyncIOScheduler` and the
  job registration table.
* :data:`scheduler` — module-level singleton (one scheduler per
  process).
* :func:`register_scheduler` — convenience that calls
  :meth:`TaskScheduler.setup` on either the singleton or a provided
  instance and returns the configured (but not yet started) scheduler.
* The individual job coroutines (:func:`check_expired_tasks`,
  :func:`send_task_reminders`, :func:`daily_summary_report`) for testing
  / direct invocation.

Typical usage in the bot's main entry point::

    from app.scheduler import register_scheduler, scheduler

    register_scheduler()          # wire jobs on the singleton
    await scheduler.start()       # then start polling (or before)
    ...
    await scheduler.shutdown()
"""

from __future__ import annotations

from typing import Optional

from app.scheduler.jobs import (
    check_expired_tasks,
    daily_summary_report,
    send_task_reminders,
)
from app.scheduler.scheduler import TaskScheduler, scheduler

__all__ = [
    "TaskScheduler",
    "scheduler",
    "register_scheduler",
    "check_expired_tasks",
    "send_task_reminders",
    "daily_summary_report",
]


def register_scheduler(
    scheduler_instance: Optional[TaskScheduler] = None,
) -> TaskScheduler:
    """Register jobs on (and return) a :class:`TaskScheduler` instance.

    Convenience used by the bot's main entry point::

        from app.scheduler import register_scheduler, scheduler

        sched = register_scheduler()
        await sched.start()

    The returned scheduler is configured (jobs added) but NOT started —
    the caller is responsible for calling :meth:`TaskScheduler.start`
    from within a running asyncio loop.

    Args:
        scheduler_instance: Optional scheduler instance to (re-)setup.
            When ``None`` (default) the module-level singleton
            :data:`scheduler` is used and returned.

    Returns:
        The configured (but not yet started) scheduler instance.
    """
    instance: TaskScheduler = (
        scheduler_instance if scheduler_instance is not None else scheduler
    )
    instance.setup()
    return instance
