"""激励计算 — 计算连击、反馈策略。"""
from datetime import date, datetime, timedelta
from typing import Any, Optional


class StreakData:
    """Simple value object for streak tracking."""

    def __init__(self) -> None:
        self.current_streak: int = 0          # Consecutive days with activity
        self.best_streak: int = 0
        self.last_activity: Optional[datetime] = None
        self.consecutive_correct: int = 0     # Correct answers today

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_streak": self.current_streak,
            "best_streak": self.best_streak,
            "consecutive_correct": self.consecutive_correct,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


class RewardsCalculator:
    """ incentive system for learning streaks and feedback strategies."""

    def __init__(self) -> None:
        self._streaks: dict[str, StreakData] = {}

    def _get_or_create(self, user_id: str, topic_id: str) -> StreakData:
        key = f"{user_id}_{topic_id}"
        if key not in self._streaks:
            self._streaks[key] = StreakData()
        return self._streaks[key]

    def calculate_streak(self, user_id: str, topic_id: str, is_completed: bool) -> dict[str, Any]:
        """Update streak data and return encouragement info.

        Streak rules:
        - ``current_streak``: number of consecutive *days* with learning activity.
        - ``consecutive_correct``: number of consecutive *correct answers today*.
        """
        data = self._get_or_create(user_id, topic_id)
        today = datetime.now().date()

        if not is_completed:
            # No change, just return current state
            return {
                **data.to_dict(),
                "encouragement": self._get_encouragement_message(data.consecutive_correct),
            }

        # First ever activity
        if data.last_activity is None:
            data.current_streak = 1
            data.consecutive_correct = 1
            data.last_activity = datetime.now()
            data.best_streak = max(data.best_streak, data.current_streak)
            return {
                **data.to_dict(),
                "encouragement": self._get_encouragement_message(data.consecutive_correct),
            }

        last_date = data.last_activity.date()

        if last_date == today:
            # Same day — increment consecutive correct counter only
            data.consecutive_correct += 1
        elif last_date == today - timedelta(days=1):
            # Consecutive day — bump streak, reset daily counter
            data.current_streak += 1
            data.consecutive_correct = 1
            data.last_activity = datetime.now()
        else:
            # Streak broken — reset
            data.current_streak = 1
            data.consecutive_correct = 1
            data.last_activity = datetime.now()

        data.best_streak = max(data.best_streak, data.current_streak)

        return {
            **data.to_dict(),
            "encouragement": self._get_encouragement_message(data.consecutive_correct),
        }

    @staticmethod
    def _get_encouragement_message(consecutive_correct: int) -> str:
        """Return an encouragement message based on today's consecutive correct answers."""
        if consecutive_correct >= 10:
            return "🌟 太厉害了！你已经连续答对 10 题！"
        if consecutive_correct >= 5:
            return "🔥 连续答对 5 题，势头正旺！"
        if consecutive_correct >= 3:
            return "👍 连续答对 3 题，继续保持！"
        if consecutive_correct >= 2:
            return "💪 连续答对 2 题，好样的！"
        return ""

    @staticmethod
    def get_feedback_strategy(fail_count: int, hint_level: int, max_hint_level: int = 4) -> dict[str, bool]:
        """Return a feedback strategy dict based on the learner's current state.

        Args:
            fail_count: How many times the user has answered incorrectly.
            hint_level: Current hint level (0 = no hint yet).
            max_hint_level: Maximum hint level before giving the answer.
        """
        return {
            "show_encouragement": fail_count == 0,
            "use_gentle_feedback": fail_count == 1,
            "use_hint": fail_count >= 2 and hint_level < max_hint_level,
            "allow_direct": hint_level >= max_hint_level,
            "praise_progress": fail_count > 0 and fail_count % 3 == 0,
        }
