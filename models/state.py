"""Learning state model."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class LearningStatus(str, Enum):
    """Learning status enumeration."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    MASTERED = "mastered"
    NEEDS_REVIEW = "needs_review"


class ChunkState(BaseModel):
    """State for a single knowledge chunk."""

    chunk_id: str
    title: str = Field(default="", description="Knowledge point title")
    content: str = Field(default="", description="Knowledge point content")
    question: str = Field(default="", description="Validation question")
    options: Optional[List[str]] = Field(default=None, description="Optional multiple choice options")
    correct_answer: str = Field(default="", description="Correct answer")
    analogy: Optional[str] = Field(default=None, description="Life analogy for hints")
    difficulty: str = Field(default="medium", description="Difficulty: easy, medium, hard")

    # Learning progress
    status: LearningStatus = LearningStatus.NOT_STARTED
    fail_count: int = Field(default=0, description="Number of incorrect attempts")
    hint_level: int = Field(default=0, description="Current hint level: 0=none, 1=clue, 2=analogy, 3=semi-analysis, 4=answer")
    attempts: int = Field(default=0, description="Total answer attempts")
    mastered_at: Optional[datetime] = Field(default=None, description="When the chunk was mastered")


class TopicState(BaseModel):
    """State for a learning topic."""

    topic_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    current_chunk_index: int = Field(default=0, description="Index of current chunk being studied")
    total_chunks: int = Field(default=0, description="Total number of chunks")
    chunks: List[ChunkState] = Field(default_factory=list, description="List of knowledge chunks")
    is_completed: bool = Field(default=False, description="Whether the topic is fully completed")

    model_config = {
        "json_schema_extra": {
            "example": {
                "topic_id": "topic_001",
                "user_id": "user_001",
                "current_chunk_index": 0,
                "total_chunks": 5,
                "is_completed": False,
                "chunks": [
                    {
                        "chunk_id": "topic_001_chunk_0",
                        "title": "Transformer的基本原理",
                        "content": "Transformer是一种...",
                        "question": "Transformer的核心机制是什么？",
                        "options": ["A. CNN", "B. 注意力机制", "C. RNN", "D. 全连接层"],
                        "correct_answer": "B",
                        "analogy": "就像...",
                        "difficulty": "medium",
                        "status": "not_started",
                    }
                ],
            }
        }
    }
