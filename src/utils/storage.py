"""主题隔离存储 — 负责创建和管理隔离的 Topic 文件夹。"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.utils.config import get_config


class _JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def save_json(file_path: Path, data: dict) -> None:
    """Save data as a JSON file with UTF-8 encoding."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, cls=_JSONEncoder)


def load_json(file_path: Path) -> Optional[dict]:
    """Load a JSON file. Returns None if the file does not exist."""
    if not file_path.exists():
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TopicStorage:
    """Topic-isolated storage manager.

    Each user's learning data is stored in a separate directory:
    data/users/{user_id}/
    ├── profile.json
    ├── index.json
    └── topics/{topic_id}/
        ├── state.json
        ├── history.json
        └── chunks/
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        base = get_config().paths.data_path
        self.user_dir = base / "users" / user_id
        self.topics_dir = self.user_dir / "topics"

    def _topic_dir(self, topic_id: str) -> Path:
        """Return the directory path for a given topic."""
        return self.topics_dir / topic_id

    def _ensure_topic_dir(self, topic_id: str) -> Path:
        """Ensure the topic directory (including chunks subdir) exists."""
        topic_dir = self._topic_dir(topic_id)
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "chunks").mkdir(exist_ok=True)
        return topic_dir

    # ─── Topic State ───

    def save_topic_state(self, topic_id: str, state: dict) -> None:
        """Save topic state to state.json."""
        save_json(self._ensure_topic_dir(topic_id) / "state.json", state)

    def load_topic_state(self, topic_id: str) -> Optional[dict]:
        """Load topic state from state.json."""
        return load_json(self._topic_dir(topic_id) / "state.json")

    # ─── Conversation History ───

    def save_conversation_history(self, topic_id: str, history: list) -> None:
        """Save conversation history to history.json."""
        save_json(
            self._ensure_topic_dir(topic_id) / "history.json", {"messages": history}
        )

    def load_conversation_history(self, topic_id: str) -> Optional[dict]:
        """Load conversation history from history.json."""
        return load_json(self._topic_dir(topic_id) / "history.json")

    # ─── User Profile ───

    def save_user_profile(self, profile: dict) -> None:
        """Save user profile to profile.json."""
        self.user_dir.mkdir(parents=True, exist_ok=True)
        save_json(self.user_dir / "profile.json", profile)

    def load_user_profile(self) -> Optional[dict]:
        """Load user profile from profile.json."""
        return load_json(self.user_dir / "profile.json")

    # ─── Learning Index ───

    def save_learning_index(self, index: dict) -> None:
        """Save learning index to index.json."""
        self.user_dir.mkdir(parents=True, exist_ok=True)
        save_json(self.user_dir / "index.json", index)

    def load_learning_index(self) -> Optional[dict]:
        """Load learning index from index.json."""
        return load_json(self.user_dir / "index.json")

    # ─── Topic Listing ───

    def list_topics(self) -> list[str]:
        """Return a list of all topic IDs for the user."""
        if not self.topics_dir.exists():
            return []
        return [d.name for d in self.topics_dir.iterdir() if d.is_dir()]
