"""Utility package: date, formatting, security and export helpers.

Re-exports the most commonly used helpers so callers can do::

    from app.utils import now_utc, escape_html, validate_employee_code
"""

from __future__ import annotations

from app.utils.dates import (
    build_deadline,
    end_of_today_local,
    format_date,
    format_datetime,
    now_local,
    now_utc,
    parse_date,
    parse_time,
    remaining_time,
    start_of_month_local,
    start_of_today_local,
    start_of_week_local,
    to_local,
)
from app.utils.export import (
    stats_to_excel_bytes,
    tasks_to_excel_bytes,
    tasks_to_pdf_bytes,
)
from app.utils.formatting import (
    centered,
    divider,
    employee_card,
    escape_html,
    progress_bar,
    stats_card,
    task_card,
)
from app.utils.security import (
    generate_secure_token,
    is_safe_int,
    mask_phone,
    sanitize_text,
    validate_employee_code,
)

__all__ = [
    # dates
    "build_deadline",
    "end_of_today_local",
    "format_date",
    "format_datetime",
    "now_local",
    "now_utc",
    "parse_date",
    "parse_time",
    "remaining_time",
    "start_of_month_local",
    "start_of_today_local",
    "start_of_week_local",
    "to_local",
    # formatting
    "centered",
    "divider",
    "employee_card",
    "escape_html",
    "progress_bar",
    "stats_card",
    "task_card",
    # security
    "generate_secure_token",
    "is_safe_int",
    "mask_phone",
    "sanitize_text",
    "validate_employee_code",
    # export
    "stats_to_excel_bytes",
    "tasks_to_excel_bytes",
    "tasks_to_pdf_bytes",
]
