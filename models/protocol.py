"""Protocol model - defines AI response structure."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    """AI response type enumeration."""
    EXPLANATION = "explanation"
    QUESTION = "question"
    FEEDBACK_CORRECT = "feedback_correct"
    FEEDBACK_WRONG = "feedback_wrong"
    FEEDBACK_HINT = "feedback_hint"
    DIRECT_ANSWER = "direct_answer"


class AIMessage(BaseModel):
    """Protocol model - defines the required fields for AI responses."""

    response_type: ResponseType
    content: str = Field(description="The main content to display to user")
    chunk_id: Optional[str] = None
    question: Optional[str] = Field(default=None, description="Question to ask user")
    options: Optional[List[str]] = Field(
        default=None, description="Multiple choice options if applicable"
    )
    correct_answer: Optional[str] = Field(
        default=None, description="Correct answer for validation"
    )
    hint_level: int = Field(
        default=0, description="Current hint level: 0=none, 1=clue, 2=analogy, 3=semi-analysis"
    )
    is_final: bool = Field(
        default=False, description="Whether this is a final answer in quick mode"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "response_type": "question",
                "content": "现在你已经了解了什么是大语言模型，让我来验证一下你的理解：",
                "chunk_id": "chunk_001",
                "question": "大语言模型的核心能力是什么？",
                "options": [
                    "A. 图像识别",
                    "B. 文本生成与推理",
                    "C. 语音合成",
                    "D. 视频处理",
                ],
                "correct_answer": "B",
                "hint_level": 0,
            }
        }
    }


class UserAnswer(BaseModel):
    """User answer model for validation."""

    chunk_id: str
    answer: str
    is_direct: bool = Field(default=False, description="Whether user used /direct command")
    timestamp: Optional[datetime] = Field(default=None, description="Answer submission time")
