"""Tests for main.py CLI control flow."""

from unittest.mock import Mock

import main
from models.protocol import AIMessage, ResponseType
from models.state import ChunkState, TopicState


class DummyLogger:
    """Logger stub used by TeacherSkillApp tests."""

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class FakeStorage:
    """Storage stub for resume-flow tests."""

    def __init__(self, topic_state: TopicState):
        self.topic_state = topic_state

    def load_topic_state(self, topic_id: str) -> dict:
        return self.topic_state.model_dump(mode="json")

    def load_conversation_history(self, topic_id: str) -> dict:
        return {"messages": [{"role": "user", "content": "previous answer"}]}


class FakeEngine:
    """Engine stub that simulates one final answer flow."""

    def __init__(
        self,
        answer_response: AIMessage | None = None,
        next_response: AIMessage | None = None,
    ):
        self.start_topic_calls = 0
        self.receive_answer_calls: list[tuple[str, bool]] = []
        self.next_chunk_calls = 0
        self.restored_messages: list[dict] = []
        self.topic_state: TopicState | None = None
        self.memory = type("Memory", (), {"messages": []})()
        self.answer_response = answer_response or AIMessage(
            response_type=ResponseType.FEEDBACK_CORRECT,
            content="correct",
        )
        self.next_response = next_response or AIMessage(
            response_type=ResponseType.EXPLANATION,
            content="done",
            is_final=True,
        )

    def start_topic(self, topic_state: TopicState) -> AIMessage:
        self.start_topic_calls += 1
        self.topic_state = topic_state
        return AIMessage(
            response_type=ResponseType.QUESTION,
            content="teach",
            question="question?",
        )

    def receive_answer(self, answer: str, is_direct: bool = False) -> AIMessage:
        self.receive_answer_calls.append((answer, is_direct))
        return self.answer_response

    def next_chunk(self) -> AIMessage:
        self.next_chunk_calls += 1
        if self.topic_state:
            self.topic_state.is_completed = True
        return self.next_response

    def restore_memory(self, messages: list[dict]) -> None:
        self.restored_messages = messages


def make_topic_state() -> TopicState:
    """Create a minimal topic state for main-flow tests."""
    return TopicState(
        topic_id="topic_test",
        user_id="user_test",
        total_chunks=1,
        chunks=[
            ChunkState(
                chunk_id="chunk_1",
                title="Chunk 1",
                content="Content",
                question="Question?",
                correct_answer="A",
            )
        ],
    )


def make_app(engine: FakeEngine | None = None):
    """Create a TeacherSkillApp instance without running __init__."""
    app = main.TeacherSkillApp.__new__(main.TeacherSkillApp)
    app.user_id = "user_test"
    app.current_engine = engine
    app.logger = DummyLogger()
    return app


class TestResumeTopicFlow:
    """Tests for resuming existing topics."""

    def test_resume_topic_does_not_start_topic_before_learning_loop(self, monkeypatch):
        topic_state = make_topic_state()
        created_engines: list[FakeEngine] = []

        def fake_engine_factory(user_id: str, topic_id: str) -> FakeEngine:
            engine = FakeEngine()
            created_engines.append(engine)
            return engine

        app = make_app()
        app.storage = FakeStorage(topic_state)
        app._learning_loop = Mock()
        app._show_summary = Mock()

        monkeypatch.setattr(main, "TutorEngine", fake_engine_factory)

        app._resume_topic("topic_test")

        assert len(created_engines) == 1
        assert created_engines[0].start_topic_calls == 0
        assert created_engines[0].restored_messages == [
            {"role": "user", "content": "previous answer"}
        ]
        app._learning_loop.assert_called_once()
        app._show_summary.assert_called_once()


class TestLearningLoopCompletion:
    """Tests for learning-loop completion behavior."""

    def test_correct_answer_on_final_chunk_breaks_learning_loop(self, monkeypatch):
        topic_state = make_topic_state()
        engine = FakeEngine()
        app = make_app(engine)
        displayed: list[AIMessage] = []
        app._display_response = displayed.append

        inputs = iter(["A"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        assert engine.start_topic_calls == 1
        assert engine.receive_answer_calls == [("A", False)]
        assert engine.next_chunk_calls == 1
        assert displayed[-1].is_final is True

    def test_direct_answer_on_final_chunk_breaks_learning_loop(self, monkeypatch):
        topic_state = make_topic_state()
        engine = FakeEngine(
            answer_response=AIMessage(
                response_type=ResponseType.DIRECT_ANSWER,
                content="direct",
                is_final=True,
            )
        )
        app = make_app(engine)
        displayed: list[AIMessage] = []
        app._display_response = displayed.append

        inputs = iter(["/direct"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after /direct completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        assert engine.start_topic_calls == 1
        assert engine.receive_answer_calls == [("", True)]
        assert engine.next_chunk_calls == 1
        assert displayed[-1].is_final is True
