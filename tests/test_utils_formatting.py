"""Tests for app.utils.formatting — HTML card helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models.enums import TaskPriority
from app.utils import formatting


def test_escape_html() -> None:
    assert formatting.escape_html("<b>&") == "&lt;b&gt;&amp;"
    assert formatting.escape_html(None) == ""  # type: ignore[arg-type]


def test_escape_html_in_card_is_applied() -> None:
    task = SimpleNamespace(
        title="<script>x</script>",
        description="normal",
        priority=TaskPriority.MEDIUM,
        deadline=datetime.now(timezone.utc) + timedelta(hours=5),
    )
    card = formatting.task_card(task)
    assert "<script>" not in card
    assert "&lt;script&gt;" in card


def test_task_card_renders_fields() -> None:
    task = SimpleNamespace(
        title="Deploy",
        description="Prod deploy",
        priority=TaskPriority.URGENT,
        deadline=datetime(2025, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    card = formatting.task_card(task, header="📌 Yangi vazifa")
    assert "📌 Yangi vazifa" in card
    assert "Deploy" in card
    assert "🔴" in card  # urgent emoji


def test_task_card_accepts_string_priority() -> None:
    task = SimpleNamespace(
        title="T",
        description=None,
        priority="high",
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
    )
    card = formatting.task_card(task)
    assert "🟠" in card  # high emoji


def test_progress_bar_bounds() -> None:
    assert formatting.progress_bar(-10) == "░" * 10
    assert formatting.progress_bar(150) == "█" * 10
    bar = formatting.progress_bar(50, width=4)
    assert bar.count("█") == 2
    assert bar.count("░") == 2


def test_divider() -> None:
    assert "━" in formatting.divider()


def test_stats_card_renders_success_rate() -> None:
    card = formatting.stats_card({"completed": 10, "expired": 2, "success_rate": 83.3})
    assert "83" in card
    assert "10" in card
