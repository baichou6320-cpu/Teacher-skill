"""Tests for main.py CLI control flow."""

from unittest.mock import Mock

import main
from models.protocol import AIMessage, ResponseType
from models.state import ChunkState, LearningStatus, TopicState


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
        self.skip_calls = 0
        self.back_calls = 0
        self.jump_calls: list[int] = []
        self.restored_messages: list[dict] = []
        self.topic_state: TopicState | None = None
        self.memory = type("Memory", (), {"messages": []})()
        self.answer_response = answer_response or AIMessage(
            response_type=ResponseType.FEEDBACK_CORRECT,
            content="correct",
        )
        self.next_response = next_response

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
        if self.next_response is not None:
            if self.topic_state and self.next_response.is_final:
                self.topic_state.is_completed = True
            return self.next_response
        if self.topic_state:
            self.topic_state.current_chunk_index += 1
            if self.topic_state.current_chunk_index >= self.topic_state.total_chunks:
                self.topic_state.is_completed = True
                return AIMessage(
                    response_type=ResponseType.EXPLANATION,
                    content="done",
                    is_final=True,
                )
            return AIMessage(
                response_type=ResponseType.QUESTION,
                content="teach next",
                question=f"question {self.topic_state.current_chunk_index + 1}?",
            )
        return AIMessage(
            response_type=ResponseType.EXPLANATION,
            content="done",
            is_final=True,
        )

    def restore_memory(self, messages: list[dict]) -> None:
        self.restored_messages = messages

    def append_material(self, material: str, user_level: str = "beginner") -> list[ChunkState]:
        if not self.topic_state:
            return []
        chunk = ChunkState(
            chunk_id="chunk_appended",
            title="Appended",
            content=material,
            question="Appended question?",
            correct_answer="A",
        )
        self.topic_state.chunks.append(chunk)
        self.topic_state.total_chunks = len(self.topic_state.chunks)
        return [chunk]

    def skip_current_chunk(self) -> AIMessage:
        self.skip_calls += 1
        if self.topic_state:
            self.topic_state.chunks[
                self.topic_state.current_chunk_index
            ].status = LearningStatus.NEEDS_REVIEW
        return self.next_chunk()

    def previous_chunk(self) -> AIMessage:
        self.back_calls += 1
        if not self.topic_state or self.topic_state.current_chunk_index <= 0:
            return AIMessage(
                response_type=ResponseType.EXPLANATION,
                content="already first",
            )
        self.topic_state.current_chunk_index -= 1
        return AIMessage(
            response_type=ResponseType.QUESTION,
            content="teach previous",
            question=f"question {self.topic_state.current_chunk_index + 1}?",
        )

    def jump_to_chunk(self, chunk_number: int) -> AIMessage:
        self.jump_calls.append(chunk_number)
        if not self.topic_state:
            raise ValueError("Topic state not initialized")
        if chunk_number < 1 or chunk_number > self.topic_state.total_chunks:
            raise ValueError("invalid chunk")
        self.topic_state.current_chunk_index = chunk_number - 1
        return AIMessage(
            response_type=ResponseType.QUESTION,
            content="teach jumped",
            question=f"question {chunk_number}?",
        )


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


def make_multi_topic_state() -> TopicState:
    """Create a three-chunk topic state for navigation tests."""
    return TopicState(
        topic_id="topic_test",
        user_id="user_test",
        total_chunks=3,
        chunks=[
            ChunkState(
                chunk_id=f"chunk_{i}",
                title=f"Chunk {i}",
                content=f"Content {i}",
                question=f"Question {i}?",
                correct_answer="A",
            )
            for i in range(1, 4)
        ],
    )


def make_app(engine: FakeEngine | None = None):
    """Create a TeacherSkillApp instance without running __init__."""
    app = main.TeacherSkillApp.__new__(main.TeacherSkillApp)
    app.user_id = "user_test"
    app.current_engine = engine
    app.user_level = "beginner"
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

    def test_load_command_appends_material_without_submitting_answer(self, monkeypatch):
        topic_state = make_topic_state()
        engine = FakeEngine(
            next_response=AIMessage(
                response_type=ResponseType.EXPLANATION,
                content="done",
                is_final=True,
            )
        )
        app = make_app(engine)
        displayed: list[AIMessage] = []
        app._display_response = displayed.append
        app._load_material_from_file = Mock(return_value="new material")
        app._show_append_result = Mock()
        app._save_progress = Mock()

        inputs = iter(["/load notes.md", "A"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        app._load_material_from_file.assert_called_once_with("notes.md")
        app._show_append_result.assert_called_once()
        app._save_progress.assert_called_once()
        assert engine.receive_answer_calls == [("A", False)]
        assert engine.next_chunk_calls == 1

    def test_skip_marks_current_chunk_review_and_does_not_submit_answer(self, monkeypatch):
        topic_state = make_multi_topic_state()
        engine = FakeEngine()
        app = make_app(engine)
        app._display_response = Mock()
        app._save_progress = Mock()

        inputs = iter(["/skip", "A", "A"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        assert engine.skip_calls == 1
        assert topic_state.chunks[0].status == LearningStatus.NEEDS_REVIEW
        assert engine.receive_answer_calls == [("A", False), ("A", False)]

    def test_back_command_reteaches_previous_chunk_without_submitting_answer(self, monkeypatch):
        topic_state = make_multi_topic_state()
        topic_state.current_chunk_index = 1
        engine = FakeEngine()
        app = make_app(engine)
        app._display_response = Mock()
        app._save_progress = Mock()

        inputs = iter(["/back", "A", "A", "A"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        assert engine.back_calls == 1
        assert engine.receive_answer_calls == [
            ("A", False),
            ("A", False),
            ("A", False),
        ]

    def test_jump_command_moves_to_requested_chunk_without_submitting_answer(self, monkeypatch):
        topic_state = make_multi_topic_state()
        engine = FakeEngine()
        app = make_app(engine)
        app._display_response = Mock()
        app._save_progress = Mock()

        inputs = iter(["/jump 3", "A"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        assert engine.jump_calls == [3]
        assert engine.receive_answer_calls == [("A", False)]

    def test_list_review_and_invalid_jump_do_not_submit_answer(self, monkeypatch):
        topic_state = make_multi_topic_state()
        topic_state.chunks[0].status = LearningStatus.NEEDS_REVIEW
        engine = FakeEngine()
        app = make_app(engine)
        app._display_response = Mock()
        app._save_progress = Mock()

        inputs = iter(["/list", "/review", "/jump nope", "A", "A", "A"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        assert engine.jump_calls == []
        assert engine.receive_answer_calls == [
            ("A", False),
            ("A", False),
            ("A", False),
        ]


class TestMaterialInput:
    """Tests for improved material input flow."""

    def test_parse_load_command_supports_quoted_path(self):
        app = make_app()

        assert app._parse_load_command('/load "docs/sample article.md"') == "docs/sample article.md"

    def test_single_line_material_does_not_require_done(self, monkeypatch):
        app = make_app()
        monkeypatch.setattr(
            main.console,
            "input",
            lambda prompt: "Transformer 是一种基于注意力机制的模型",
        )

        material = app._collect_material_interactively()

        assert material == "Transformer 是一种基于注意力机制的模型"

    def test_load_command_can_start_new_topic_material(self, monkeypatch):
        app = make_app()
        app._load_material_from_file = Mock(return_value="file material")
        monkeypatch.setattr(main.console, "input", lambda prompt: "/load article.md")

        material = app._collect_material_interactively()

        assert material == "file material"
        app._load_material_from_file.assert_called_once_with("article.md")
