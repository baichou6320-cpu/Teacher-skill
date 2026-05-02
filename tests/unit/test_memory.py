"""Tests for src/core/memory.py."""

import pytest

from src.core.memory import ConversationMemory, GlobalMemory
from models.protocol import AIMessage, UserAnswer, ResponseType


class TestConversationMemory:
    """Tests for ConversationMemory."""

    def test_add_ai_message(self):
        mem = ConversationMemory("u1", "t1")
        msg = AIMessage(response_type=ResponseType.EXPLANATION, content="hello")
        mem.add_ai_message(msg)
        assert len(mem.messages) == 1
        assert mem.messages[0]["role"] == "assistant"
        assert mem.messages[0]["content"] == "hello"
        assert mem.messages[0]["type"] == "explanation"
        assert "timestamp" in mem.messages[0]

    def test_add_user_message(self):
        mem = ConversationMemory("u1", "t1")
        mem.add_user_message("my answer")
        assert len(mem.messages) == 1
        assert mem.messages[0]["role"] == "user"
        assert mem.messages[0]["content"] == "my answer"

    def test_add_user_message_with_answer(self):
        mem = ConversationMemory("u1", "t1")
        ans = UserAnswer(chunk_id="c1", answer="A")
        mem.add_user_message("A", answer=ans)
        assert mem.messages[0]["answer"] == "A"
        assert mem.messages[0]["is_direct"] is False

    def test_add_user_message_direct(self):
        mem = ConversationMemory("u1", "t1")
        ans = UserAnswer(chunk_id="c1", answer="B", is_direct=True)
        mem.add_user_message("/direct B", answer=ans)
        assert mem.messages[0]["is_direct"] is True

    def test_get_recent_history(self):
        mem = ConversationMemory("u1", "t1")
        for i in range(15):
            mem.add_user_message(str(i))
        recent = mem.get_recent_history(5)
        assert len(recent) == 5
        assert recent[-1]["content"] == "14"

    def test_get_recent_history_more_than_total(self):
        mem = ConversationMemory("u1", "t1")
        mem.add_user_message("only one")
        recent = mem.get_recent_history(10)
        assert len(recent) == 1

    def test_get_context_for_llm(self):
        mem = ConversationMemory("u1", "t1")
        msg = AIMessage(response_type=ResponseType.EXPLANATION, content="hi")
        mem.add_ai_message(msg)
        mem.add_user_message("hello")
        ctx = mem.get_context_for_llm(5)
        assert "助手: hi" in ctx
        assert "用户: hello" in ctx

    def test_get_context_for_llm_empty(self):
        mem = ConversationMemory("u1", "t1")
        ctx = mem.get_context_for_llm(5)
        assert ctx == ""

    def test_load_from_history(self):
        mem = ConversationMemory("u1", "t1")
        mem.load_from_history([{"role": "user", "content": "prev"}])
        assert len(mem.messages) == 1
        assert mem.messages[0]["content"] == "prev"

    def test_clear(self):
        mem = ConversationMemory("u1", "t1")
        mem.add_user_message("x")
        mem.clear()
        assert mem.messages == []

    def test_get_summary(self):
        mem = ConversationMemory("u1", "t1")
        mem.add_user_message("x")
        summary = mem.get_summary()
        assert summary["user_id"] == "u1"
        assert summary["topic_id"] == "t1"
        assert summary["message_count"] == 1
        assert "created_at" in summary


class TestGlobalMemory:
    """Tests for GlobalMemory."""

    def test_set_and_get(self):
        gm = GlobalMemory()
        gm.set("u1", "difficulty", "hard")
        assert gm.get("u1", "difficulty") == "hard"

    def test_get_default(self):
        gm = GlobalMemory()
        assert gm.get("u1", "missing") is None
        assert gm.get("u1", "missing", "default") == "default"

    def test_multiple_users_isolated(self):
        gm = GlobalMemory()
        gm.set("u1", "key", "val1")
        gm.set("u2", "key", "val2")
        assert gm.get("u1", "key") == "val1"
        assert gm.get("u2", "key") == "val2"
