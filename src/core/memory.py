"""记忆管理器 — 处理短期对话历史，解决对话过程中的"失忆"问题。"""
from datetime import datetime
from typing import Any, Optional

from models.protocol import AIMessage, UserAnswer


class ConversationMemory:
    """Short-term conversation memory for the current topic."""

    def __init__(self, user_id: str, topic_id: str):
        self.user_id = user_id
        self.topic_id = topic_id
        self.messages: list[dict[str, Any]] = []
        self.created_at = datetime.now()

    def add_ai_message(self, message: AIMessage) -> None:
        """Append an AI message to the history."""
        self.messages.append({
            "role": "assistant",
            "type": message.response_type.value,
            "content": message.content,
            "chunk_id": message.chunk_id,
            "timestamp": datetime.now().isoformat(),
        })

    def add_user_message(self, content: str, answer: Optional[UserAnswer] = None) -> None:
        """Append a user message to the history."""
        msg: dict[str, Any] = {
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if answer:
            msg["answer"] = answer.answer
            msg["is_direct"] = answer.is_direct
        self.messages.append(msg)

    def get_recent_history(self, count: int = 10) -> list[dict[str, Any]]:
        """Return the most recent *count* messages."""
        return self.messages[-count:]

    def get_context_for_llm(self, count: int = 5) -> str:
        """Format recent messages for injection into an LLM prompt."""
        recent = self.get_recent_history(count)
        lines: list[str] = []
        for msg in recent:
            role = "助手" if msg["role"] == "assistant" else "用户"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def load_from_history(self, messages: list[dict[str, Any]]) -> None:
        """Restore memory from a persisted history list."""
        self.messages = list(messages)

    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()

    def get_summary(self) -> dict[str, Any]:
        """Return a summary of the memory state."""
        return {
            "user_id": self.user_id,
            "topic_id": self.topic_id,
            "message_count": len(self.messages),
            "created_at": self.created_at.isoformat(),
        }


class GlobalMemory:
    """Global (cross-topic) memory for user preferences."""

    def __init__(self) -> None:
        self._prefs: dict[str, dict[str, Any]] = {}

    def set(self, user_id: str, key: str, value: Any) -> None:
        """Store a user preference."""
        self._prefs.setdefault(user_id, {})[key] = value

    def get(self, user_id: str, key: str, default: Any = None) -> Any:
        """Retrieve a user preference."""
        return self._prefs.get(user_id, {}).get(key, default)
