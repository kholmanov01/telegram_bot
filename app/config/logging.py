"""Loguru logging configuration with rotating, separated log files.

Three separate sinks are configured:
  * ``logs/info.log``     — INFO and above (general flow).
  * ``logs/warning.log``  — WARNING and above.
  * ``logs/error.log``    — ERROR and above.

A console sink is also added for development visibility. Uvicorn/Aiogram
loggers are intercepted so that all logs flow through Loguru.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from loguru import logger

from app.config.settings import settings


class InterceptHandler(logging.Handler):
    """Forward records from the standard ``logging`` module to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        # Get corresponding Loguru level if it exists.
        try:
            level: str | int = logger.level(record.levelname).name
        except (ValueError, AttributeError):
            level = record.levelno

        # Find caller from where the original message originated.
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _format_record(record: dict[str, Any]) -> str:
    """Custom log format including extra fields."""
    extra: dict[str, Any] = record.get("extra", {})
    extra_str = " | ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    if extra_str:
        fmt += f" | <dim>{extra_str}</dim>"
    return fmt + "\n"


def setup_logging() -> None:
    """Configure Loguru sinks and intercept standard logging.

    Idempotent: calling it multiple times is safe.
    """
    logger.remove()

    log_level = settings.log_level.upper()
    logs_dir = settings.logs_dir

    # --- Console sink ---
    logger.add(
        sys.stdout,
        level=log_level,
        format=_format_record,
        colorize=True,
        backtrace=True,
        diagnose=not settings.is_production,
    )

    # --- Rotating file sinks ---
    logger.add(
        logs_dir / "info.log",
        level="INFO",
        format=_format_record,
        rotation="20 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    logger.add(
        logs_dir / "warning.log",
        level="WARNING",
        format=_format_record,
        rotation="10 MB",
        retention="60 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    logger.add(
        logs_dir / "error.log",
        level="ERROR",
        format=_format_record,
        rotation="10 MB",
        retention="90 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=not settings.is_production,
    )

    # --- Intercept standard logging ---
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Silence noisy libraries while keeping warnings.
    for name in ("asyncio", "aiogram.event", "apscheduler"):
        logging.getLogger(name).setLevel(logging.WARNING)

    logger.info("Logging configured | env={} tz={}", settings.app_env, settings.app_timezone)
