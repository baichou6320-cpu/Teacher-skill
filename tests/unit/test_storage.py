"""Tests for src/utils/storage.py."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.utils.storage import save_json, load_json, TopicStorage
from src.utils.config import Config, PathsConfig


class TestSaveLoadJson:
    """Tests for save_json and load_json utilities."""

    def test_save_and_load(self, tmp_path):
        p = tmp_path / "data.json"
        save_json(p, {"key": "value"})
        assert load_json(p) == {"key": "value"}

    def test_load_missing_returns_none(self, tmp_path):
        assert load_json(tmp_path / "missing.json") is None

    def test_datetime_encoding(self, tmp_path):
        p = tmp_path / "dt.json"
        now = datetime(2024, 1, 15, 10, 30, 0)
        save_json(p, {"time": now})
        data = load_json(p)
        assert data["time"] == "2024-01-15T10:30:00"

    def test_nested_datetime(self, tmp_path):
        p = tmp_path / "nested.json"
        save_json(p, {"outer": {"inner": datetime(2024, 6, 1, 0, 0, 0)}})
        data = load_json(p)
        assert data["outer"]["inner"] == "2024-06-01T00:00:00"

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "deep" / "path" / "file.json"
        save_json(p, {"x": 1})
        assert p.exists()


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Return a TopicStorage instance backed by tmp_path."""
    import src.utils.config as config_module

    cfg = Config(paths=PathsConfig(data_dir=str(tmp_path)))
    monkeypatch.setattr(config_module, "_CONFIG", cfg)
    return TopicStorage("testuser")


class TestTopicStorage:
    """Tests for TopicStorage."""

    def test_save_and_load_topic_state(self, storage):
        storage.save_topic_state("topic1", {"progress": 50, "current_chunk": 2})
        loaded = storage.load_topic_state("topic1")
        assert loaded == {"progress": 50, "current_chunk": 2}

    def test_load_missing_topic_state(self, storage):
        assert storage.load_topic_state("nonexistent") is None

    def test_save_and_load_conversation_history(self, storage):
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        storage.save_conversation_history("topic1", history)
        loaded = storage.load_conversation_history("topic1")
        assert loaded["messages"] == history

    def test_load_missing_conversation_history(self, storage):
        assert storage.load_conversation_history("nonexistent") is None

    def test_save_and_load_user_profile(self, storage):
        storage.save_user_profile({"name": "Alice", "level": "beginner"})
        loaded = storage.load_user_profile()
        assert loaded == {"name": "Alice", "level": "beginner"}

    def test_load_missing_user_profile(self, storage):
        assert storage.load_user_profile() is None

    def test_save_and_load_learning_index(self, storage):
        storage.save_learning_index({"topics": ["t1", "t2"]})
        loaded = storage.load_learning_index()
        assert loaded == {"topics": ["t1", "t2"]}

    def test_load_missing_learning_index(self, storage):
        assert storage.load_learning_index() is None

    def test_list_topics_empty(self, storage):
        assert storage.list_topics() == []

    def test_list_topics(self, storage):
        storage.save_topic_state("t1", {})
        storage.save_topic_state("t2", {})
        topics = storage.list_topics()
        assert sorted(topics) == ["t1", "t2"]

    def test_topic_isolation(self, storage):
        storage.save_topic_state("topic_a", {"data": "a"})
        storage.save_topic_state("topic_b", {"data": "b"})
        assert storage.load_topic_state("topic_a") == {"data": "a"}
        assert storage.load_topic_state("topic_b") == {"data": "b"}

    def test_creates_directory_structure(self, storage, tmp_path):
        storage.save_topic_state("mytopic", {"x": 1})
        topic_dir = tmp_path / "users" / "testuser" / "topics" / "mytopic"
        assert topic_dir.exists()
        assert (topic_dir / "chunks").exists()
