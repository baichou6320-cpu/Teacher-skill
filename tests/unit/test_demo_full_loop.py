"""Tests for the deterministic boss-facing demo script."""

from io import StringIO

from rich.console import Console

import demo_full_loop
from models.state import LearningStatus


def make_test_console() -> tuple[Console, StringIO]:
    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=False,
        color_system=None,
        width=120,
    )
    return console, buffer


def test_build_demo_topic_is_fixed_three_card_loop():
    topic = demo_full_loop.build_demo_topic()

    assert topic.topic_id == demo_full_loop.DEMO_TOPIC_ID
    assert topic.total_chunks == 3
    assert [chunk.status for chunk in topic.chunks] == [
        LearningStatus.NOT_STARTED,
        LearningStatus.NOT_STARTED,
        LearningStatus.NOT_STARTED,
    ]
    assert "Transformer" in topic.title


def test_run_demo_fast_completes_expected_learning_report_without_save():
    console, buffer = make_test_console()

    summary = demo_full_loop.run_demo(
        console=console,
        delay_seconds=0,
        max_seconds=demo_full_loop.DEMO_BUDGET_SECONDS,
        save=False,
    )

    assert summary.total == 3
    assert summary.mastered == 2
    assert summary.needs_review == 1
    assert summary.history_messages >= 8
    assert summary.saved is False
    assert summary.elapsed_seconds < demo_full_loop.DEMO_BUDGET_SECONDS

    output = buffer.getvalue()
    assert "Teacher-skill 固定 3 分钟 Demo" in output
    assert "恢复验证：本次未写盘" in output
