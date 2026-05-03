"""User profile model."""
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class LearnedTopic(BaseModel):
    """A completed or archived learning topic summary."""

    topic_id: str
    title: str = ""
    summary: str = ""
    completed_at: datetime = Field(default_factory=datetime.now)
    total_chunks: int = 0
    mastered_chunks: int = 0
    review_chunks: int = 0
    source_type: str = "manual"
    source_path: str | None = None
    last_reviewed_at: datetime | None = None


class UserProfile(BaseModel):
    """User profile model."""

    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    learning_mode: str = Field(default="learning", description="'learning' or 'quick'")
    level: str = Field(default="beginner", description="'beginner' | 'intermediate' | 'advanced'")
    familiar_topics: List[str] = Field(default_factory=list)
    history_topics: List[LearnedTopic] = Field(default_factory=list)
    total_topics: int = Field(default=0)
    completed_topics: int = Field(default=0)
    streak_days: int = Field(default=0, description="Consecutive learning days")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_001",
                "learning_mode": "learning",
                "level": "intermediate",
                "familiar_topics": ["神经网络", "注意力机制"],
                "history_topics": [],
                "total_topics": 5,
                "completed_topics": 2,
                "streak_days": 3,
            }
        }
    }
