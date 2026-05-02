"""Tests for src/core/rewards.py."""

import pytest
from freezegun import freeze_time
from datetime import datetime

from src.core.rewards import RewardsCalculator, StreakData


class TestCalculateStreak:
    """Tests for RewardsCalculator.calculate_streak."""

    @freeze_time("2024-01-15 10:00:00")
    def test_first_activity(self):
        calc = RewardsCalculator()
        result = calc.calculate_streak("u1", "t1", is_completed=True)
        assert result["current_streak"] == 1
        assert result["consecutive_correct"] == 1
        assert result["best_streak"] == 1

    @freeze_time("2024-01-15 10:00:00")
    def test_same_day_multiple(self):
        calc = RewardsCalculator()
        calc.calculate_streak("u1", "t1", is_completed=True)
        result = calc.calculate_streak("u1", "t1", is_completed=True)
        assert result["current_streak"] == 1
        assert result["consecutive_correct"] == 2
        assert result["best_streak"] == 1

    @freeze_time("2024-01-15 10:00:00")
    def test_consecutive_day(self):
        calc = RewardsCalculator()
        # simulate yesterday's activity
        data = calc._get_or_create("u1", "t1")
        data.last_activity = datetime(2024, 1, 14, 10, 0, 0)
        data.current_streak = 3
        data.consecutive_correct = 2
        result = calc.calculate_streak("u1", "t1", is_completed=True)
        assert result["current_streak"] == 4
        assert result["consecutive_correct"] == 1
        assert result["best_streak"] == 4

    @freeze_time("2024-01-15 10:00:00")
    def test_streak_broken(self):
        calc = RewardsCalculator()
        data = calc._get_or_create("u1", "t1")
        data.last_activity = datetime(2024, 1, 10, 10, 0, 0)
        data.current_streak = 5
        data.best_streak = 5
        result = calc.calculate_streak("u1", "t1", is_completed=True)
        assert result["current_streak"] == 1
        assert result["consecutive_correct"] == 1
        assert result["best_streak"] == 5  # best should not decrease

    def test_not_completed_no_state_change(self):
        calc = RewardsCalculator()
        calc.calculate_streak("u1", "t1", is_completed=True)
        result = calc.calculate_streak("u1", "t1", is_completed=False)
        # state should remain from first call
        data = calc._get_or_create("u1", "t1")
        assert data.consecutive_correct == 1
        assert result["current_streak"] == 1
        assert result["consecutive_correct"] == 1

    def test_not_completed_first_call(self):
        calc = RewardsCalculator()
        result = calc.calculate_streak("u1", "t1", is_completed=False)
        assert result["current_streak"] == 0
        assert result["consecutive_correct"] == 0

    def test_multiple_topics_isolated(self):
        calc = RewardsCalculator()
        calc.calculate_streak("u1", "t1", is_completed=True)
        calc.calculate_streak("u1", "t2", is_completed=True)
        t1 = calc.calculate_streak("u1", "t1", is_completed=False)
        t2 = calc.calculate_streak("u1", "t2", is_completed=False)
        assert t1["current_streak"] == 1
        assert t2["current_streak"] == 1


class TestEncouragementMessage:
    """Tests for _get_encouragement_message thresholds."""

    def test_10_plus(self):
        assert RewardsCalculator._get_encouragement_message(10).startswith("🌟")
        assert RewardsCalculator._get_encouragement_message(15).startswith("🌟")

    def test_5_to_9(self):
        assert RewardsCalculator._get_encouragement_message(5).startswith("🔥")
        assert RewardsCalculator._get_encouragement_message(9).startswith("🔥")

    def test_3_to_4(self):
        assert RewardsCalculator._get_encouragement_message(3).startswith("👍")
        assert RewardsCalculator._get_encouragement_message(4).startswith("👍")

    def test_2(self):
        assert RewardsCalculator._get_encouragement_message(2).startswith("💪")

    def test_0_and_1(self):
        assert RewardsCalculator._get_encouragement_message(0) == ""
        assert RewardsCalculator._get_encouragement_message(1) == ""


class TestFeedbackStrategy:
    """Tests for get_feedback_strategy."""

    def test_show_encouragement(self):
        result = RewardsCalculator.get_feedback_strategy(0, 0)
        assert result["show_encouragement"] is True
        result = RewardsCalculator.get_feedback_strategy(1, 0)
        assert result["show_encouragement"] is False

    def test_use_gentle_feedback(self):
        result = RewardsCalculator.get_feedback_strategy(1, 0)
        assert result["use_gentle_feedback"] is True
        result = RewardsCalculator.get_feedback_strategy(0, 0)
        assert result["use_gentle_feedback"] is False

    def test_use_hint(self):
        result = RewardsCalculator.get_feedback_strategy(2, 1)
        assert result["use_hint"] is True
        result = RewardsCalculator.get_feedback_strategy(2, 4)
        assert result["use_hint"] is False
        result = RewardsCalculator.get_feedback_strategy(1, 1)
        assert result["use_hint"] is False

    def test_allow_direct(self):
        result = RewardsCalculator.get_feedback_strategy(5, 4)
        assert result["allow_direct"] is True
        result = RewardsCalculator.get_feedback_strategy(5, 3)
        assert result["allow_direct"] is False

    def test_praise_progress(self):
        result = RewardsCalculator.get_feedback_strategy(3, 1)
        assert result["praise_progress"] is True
        result = RewardsCalculator.get_feedback_strategy(6, 1)
        assert result["praise_progress"] is True
        result = RewardsCalculator.get_feedback_strategy(1, 1)
        assert result["praise_progress"] is False


class TestStreakData:
    """Tests for StreakData value object."""

    def test_defaults(self):
        s = StreakData()
        assert s.current_streak == 0
        assert s.best_streak == 0
        assert s.consecutive_correct == 0
        assert s.last_activity is None

    def test_to_dict(self):
        s = StreakData()
        s.current_streak = 3
        s.last_activity = datetime(2024, 1, 15, 10, 0, 0)
        d = s.to_dict()
        assert d["current_streak"] == 3
        assert d["last_activity"] == "2024-01-15T10:00:00"
