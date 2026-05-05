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

    def __init__(self, topic_state: TopicState, profile: dict | None = None):
        self.topic_state = topic_state
        self.profile = profile
        self.saved_profile: dict | None = None
        self.saved_topic_state: dict | None = None
        self.saved_history: list | None = None

    def load_topic_state(self, topic_id: str) -> dict:
        return self.topic_state.model_dump(mode="json")

    def load_conversation_history(self, topic_id: str) -> dict:
        return {"messages": [{"role": "user", "content": "previous answer"}]}

    def list_topics(self) -> list[str]:
        return [self.topic_state.topic_id]

    def load_user_profile(self) -> dict | None:
        return self.saved_profile or self.profile

    def save_user_profile(self, profile: dict) -> None:
        self.saved_profile = profile

    def save_topic_state(self, topic_id: str, state: dict) -> None:
        self.saved_topic_state = state

    def save_conversation_history(self, topic_id: str, history: list) -> None:
        self.saved_history = history


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
    main.load_runtime_dependencies()
    app = main.TeacherSkillApp.__new__(main.TeacherSkillApp)
    app.user_id = "user_test"
    app.current_engine = engine
    app.user_level = "beginner"
    app._pending_review_topic_id = None
    app.logger = DummyLogger()
    return app


class TestEnvironmentCheck:
    """Tests for the startup environment check."""

    def test_initialize_project_creates_env_and_runtime_dirs(self, tmp_path):
        (tmp_path / ".env.example").write_text(
            "ANTHROPIC_API_KEY=your_api_key_here\n",
            encoding="utf-8",
        )
        (tmp_path / "config.yaml").write_text(
            "paths:\n  data_dir: ./custom-data\n  logs_dir: ./custom-logs\n",
            encoding="utf-8",
        )
        samples_dir = tmp_path / "samples"
        samples_dir.mkdir()
        (samples_dir / "demo_article.md").write_text("demo", encoding="utf-8")

        actions, ok = main.initialize_project(project_root=tmp_path)

        assert ok is True
        assert (tmp_path / ".env").read_text(encoding="utf-8") == (
            "ANTHROPIC_API_KEY=your_api_key_here\n"
        )
        assert (tmp_path / "custom-data").is_dir()
        assert (tmp_path / "custom-logs").is_dir()
        assert any(action["item"] == ".env" and action["status"] == "已创建" for action in actions)

    def test_initialize_project_keeps_existing_env(self, tmp_path):
        (tmp_path / ".env.example").write_text(
            "ANTHROPIC_API_KEY=your_api_key_here\n",
            encoding="utf-8",
        )
        (tmp_path / ".env").write_text(
            "ANTHROPIC_API_KEY=sk-existing\n",
            encoding="utf-8",
        )

        actions, ok = main.initialize_project(project_root=tmp_path)

        assert ok is True
        assert (tmp_path / ".env").read_text(encoding="utf-8") == (
            "ANTHROPIC_API_KEY=sk-existing\n"
        )
        assert any(action["item"] == ".env" and action["status"] == "已存在" for action in actions)

    def test_collect_environment_checks_reports_missing_api_key(self, monkeypatch, tmp_path):
        (tmp_path / "config.yaml").write_text(
            "llm:\n  model_id: test-model\n",
            encoding="utf-8",
        )
        samples_dir = tmp_path / "samples"
        samples_dir.mkdir()
        (samples_dir / "demo_article.md").write_text("demo", encoding="utf-8")
        monkeypatch.setattr(main.importlib.util, "find_spec", lambda module: object())

        checks, ready = main.collect_environment_checks(env={}, project_root=tmp_path)

        api_check = next(check for check in checks if check["name"] == "ANTHROPIC_API_KEY")
        assert ready is False
        assert api_check["passed"] is False
        assert "未配置" in api_check["detail"]

    def test_collect_environment_checks_passes_when_required_items_exist(self, monkeypatch, tmp_path):
        (tmp_path / "config.yaml").write_text(
            "llm:\n  model_id: test-model\nteaching:\n  prompt_mode: split\n",
            encoding="utf-8",
        )
        samples_dir = tmp_path / "samples"
        samples_dir.mkdir()
        (samples_dir / "demo_article.md").write_text("demo", encoding="utf-8")
        monkeypatch.setattr(main.importlib.util, "find_spec", lambda module: object())

        checks, ready = main.collect_environment_checks(
            env={"ANTHROPIC_API_KEY": "sk-test"},
            project_root=tmp_path,
        )

        config_check = next(check for check in checks if check["name"] == "config.yaml")
        assert ready is True
        assert config_check["passed"] is True
        assert "test-model" in config_check["detail"]

    def test_config_check_falls_back_when_yaml_dependencies_are_missing(self, monkeypatch, tmp_path):
        (tmp_path / "config.yaml").write_text(
            "\n".join(
                [
                    "llm:",
                    '  model_id: "fallback-model"',
                    "teaching:",
                    '  prompt_mode: "split"',
                    "paths:",
                    '  data_dir: "./data"',
                    '  logs_dir: "./logs"',
                ]
            ),
            encoding="utf-8",
        )
        samples_dir = tmp_path / "samples"
        samples_dir.mkdir()
        (samples_dir / "demo_article.md").write_text("demo", encoding="utf-8")
        monkeypatch.setattr(main.importlib.util, "find_spec", lambda module: None)

        checks, ready = main.collect_environment_checks(
            env={"ANTHROPIC_API_KEY": "sk-test"},
            project_root=tmp_path,
        )

        config_check = next(check for check in checks if check["name"] == "config.yaml")
        runtime_check = next(check for check in checks if check["name"] == "运行依赖")
        assert ready is False
        assert config_check["passed"] is True
        assert "fallback-model" in config_check["detail"]
        assert "轻量解析" in config_check["detail"]
        assert runtime_check["passed"] is False


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


class TestReviewIntentSelection:
    """Tests for natural-language review entry matching."""

    def test_select_topic_can_match_review_request_from_history(self, monkeypatch):
        topic_state = make_topic_state()
        topic_state.title = "Transformer 自注意力机制"
        app = make_app()
        app.storage = FakeStorage(
            topic_state,
            profile={
                "user_id": "user_test",
                "level": "beginner",
                "history_topics": [
                    {
                        "topic_id": "topic_test",
                        "title": "Transformer 自注意力机制",
                        "summary": "理解自注意力的并行计算",
                        "completed_at": "2026-05-03T10:00:00",
                        "total_chunks": 3,
                        "mastered_chunks": 2,
                        "review_chunks": 1,
                    }
                ],
            },
        )
        monkeypatch.setattr(main.console, "input", lambda prompt: "复习一下 transformer")

        selected = app._select_topic_or_new()

        assert selected == "topic_test"
        assert app._pending_review_topic_id == "topic_test"


class TestLearningLoopCompletion:
    """Tests for learning-loop completion behavior."""

    def test_correct_answer_on_final_chunk_breaks_learning_loop(self, monkeypatch):
        topic_state = make_topic_state()
        engine = FakeEngine()
        app = make_app(engine)
        displayed: list[AIMessage] = []
        app._display_response = displayed.append

        inputs = iter(["A", ""])

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

        inputs = iter(["/load notes.md", "A", ""])

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

        inputs = iter(["/skip", "A", "", "A", ""])

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

        inputs = iter(["/back", "A", "", "A", "", "A", ""])

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

        inputs = iter(["/jump 3", "A", ""])

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

        inputs = iter(["/list", "/review", "/jump nope", "A", "", "A", "", "A", ""])

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

    def test_answer_confirmation_allows_edit_before_submit(self, monkeypatch):
        topic_state = make_topic_state()
        engine = FakeEngine()
        app = make_app(engine)
        app._display_response = Mock()

        inputs = iter(["draft answer", "/edit", "revised answer", ""])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        assert engine.receive_answer_calls == [("revised answer", False)]

    def test_answer_confirmation_can_cancel_without_submitting(self, monkeypatch):
        topic_state = make_topic_state()
        engine = FakeEngine()
        app = make_app(engine)
        app._display_response = Mock()

        inputs = iter(["draft answer", "/cancel", "final answer", ""])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration as exc:
                raise AssertionError("learning loop did not stop after completion") from exc

        monkeypatch.setattr(main.console, "input", fake_input)

        app._learning_loop(topic_state)

        assert engine.receive_answer_calls == [("final answer", False)]


class TestFeedbackDisplay:
    """Tests for answer feedback rendering helpers."""

    def test_hint_level_label_names_progressive_hint_depth(self):
        app = make_app()

        assert app._hint_level_label(1) == "线索提示"
        assert app._hint_level_label(2) == "生活类比"
        assert app._hint_level_label(3) == "半解析"
        assert app._hint_level_label(4) == "关键词/部分答案"
        assert app._hint_level_label(9) == "渐进提示"

    def test_wrong_feedback_uses_supportive_display(self):
        app = make_app()
        response = AIMessage(
            response_type=ResponseType.FEEDBACK_WRONG,
            content="hint",
            hint_level=2,
        )
        app._display_supportive_feedback = Mock()

        app._display_response(response)

        app._display_supportive_feedback.assert_called_once_with(response)


class TestHistoryArchive:
    """Tests for archived learning topic summaries."""

    def test_archive_completed_topic_updates_profile_and_deduplicates_topic(self):
        topic_state = make_multi_topic_state()
        topic_state.title = "Transformer 入门"
        topic_state.summary = "注意力机制基础"
        topic_state.source_type = "file"
        topic_state.source_path = "notes/transformer.md"
        storage = FakeStorage(
            topic_state,
            profile={
                "user_id": "user_test",
                "level": "beginner",
                "history_topics": [
                    {
                        "topic_id": "topic_test",
                        "title": "旧标题",
                        "completed_at": "2026-05-01T10:00:00",
                        "total_chunks": 1,
                        "mastered_chunks": 1,
                        "review_chunks": 0,
                    },
                    {
                        "topic_id": "topic_other",
                        "title": "其他主题",
                        "completed_at": "2026-05-01T11:00:00",
                        "total_chunks": 2,
                        "mastered_chunks": 2,
                        "review_chunks": 0,
                    },
                ],
            },
        )
        app = make_app()
        app.storage = storage

        app._archive_completed_topic(topic_state, mastered=2, needs_review=1, total=3)

        saved = storage.saved_profile
        assert saved is not None
        assert saved["total_topics"] == 2
        assert saved["completed_topics"] == 2
        assert [topic["topic_id"] for topic in saved["history_topics"]] == [
            "topic_test",
            "topic_other",
        ]
        archived = saved["history_topics"][0]
        assert archived["title"] == "Transformer 入门"
        assert archived["summary"] == "注意力机制基础"
        assert archived["total_chunks"] == 3
        assert archived["mastered_chunks"] == 2
        assert archived["review_chunks"] == 1
        assert archived["source_path"] == "notes/transformer.md"

    def test_record_review_completion_updates_profile_review_metadata(self):
        topic_state = make_multi_topic_state()
        topic_state.title = "Transformer 入门"
        topic_state.summary = "注意力机制基础"
        topic_state.source_type = "file"
        topic_state.source_path = "notes/transformer.md"
        topic_state.chunks[0].status = LearningStatus.MASTERED
        topic_state.chunks[1].status = LearningStatus.NEEDS_REVIEW
        topic_state.chunks[2].status = LearningStatus.MASTERED
        storage = FakeStorage(
            topic_state,
            profile={
                "user_id": "user_test",
                "level": "beginner",
                "history_topics": [
                    {
                        "topic_id": "topic_test",
                        "title": "旧标题",
                        "completed_at": "2026-05-01T10:00:00",
                        "total_chunks": 3,
                        "mastered_chunks": 1,
                        "review_chunks": 2,
                    }
                ],
            },
        )
        app = make_app()
        app.storage = storage

        app._record_review_completion(topic_state)

        saved = storage.saved_profile
        assert saved is not None
        archived = saved["history_topics"][0]
        assert archived["title"] == "Transformer 入门"
        assert archived["mastered_chunks"] == 2
        assert archived["review_chunks"] == 1
        assert archived["source_path"] == "notes/transformer.md"
        assert archived["last_reviewed_at"]


class TestReviewSummary:
    """Tests for review summary bookkeeping."""

    def test_record_review_result_counts_review_actions(self):
        app = make_app()
        stats = app._new_review_stats()

        app._record_review_result(
            stats,
            AIMessage(response_type=ResponseType.FEEDBACK_CORRECT, content="ok"),
        )
        app._record_review_result(
            stats,
            AIMessage(
                response_type=ResponseType.FEEDBACK_HINT,
                content="keep reviewing",
                is_final=True,
            ),
        )
        app._record_review_result(
            stats,
            AIMessage(response_type=ResponseType.DIRECT_ANSWER, content="answer"),
            is_direct=True,
        )
        app._record_review_result(
            stats,
            AIMessage(response_type=ResponseType.EXPLANATION, content="skipped"),
            is_skipped=True,
        )

        assert stats == {
            "answered": 2,
            "correct": 1,
            "direct": 1,
            "skipped": 1,
            "kept_review": 3,
        }

    def test_remaining_review_items_excludes_mastered_old_failures(self):
        app = make_app()
        topic_state = make_multi_topic_state()
        topic_state.chunks[0].status = LearningStatus.MASTERED
        topic_state.chunks[0].fail_count = 2
        topic_state.chunks[1].status = LearningStatus.NEEDS_REVIEW
        topic_state.chunks[2].fail_count = 1

        remaining = app._remaining_review_items(topic_state)

        assert [i for i, _ in remaining] == [2, 3]


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


class TestDemoMode:
    """Tests for built-in demo material flow."""

    def test_run_demo_skips_topic_selection_and_starts_demo(self):
        app = make_app()
        app.start = Mock(return_value=True)
        app._run_onboarding = Mock(return_value="beginner")
        app._start_demo_topic = Mock()
        app._select_topic_or_new = Mock()

        app.run(demo=True)

        app._start_demo_topic.assert_called_once_with("beginner")
        app._select_topic_or_new.assert_not_called()

    def test_start_demo_topic_uses_builtin_material(self):
        app = make_app()
        app._load_demo_material = Mock(return_value="demo material")
        app._start_new_topic = Mock()

        app._start_demo_topic("beginner")

        app._start_new_topic.assert_called_once_with(
            "beginner",
            material="demo material",
            source_type="demo",
        )

    def test_demo_source_label_is_readable(self):
        app = make_app()

        assert app._topic_source_label({"source_type": "demo"}) == "内置示例"

    def test_load_demo_material_reads_sample_article(self):
        app = make_app()

        material = app._load_demo_material()

        assert material is not None
        assert "番茄工作法" in material


class TestTopicMetadata:
    """Tests for readable topic metadata helpers."""

    def test_apply_topic_metadata_uses_file_stem_when_title_missing(self):
        app = make_app()
        topic_state = make_multi_topic_state()
        topic_state.title = ""
        topic_state.summary = ""

        app._apply_topic_metadata(
            topic_state,
            "Transformer notes",
            source_path="docs/Transformer 入门.md",
        )

        assert topic_state.title == "Transformer 入门"
        assert topic_state.summary == "Chunk 1、Chunk 2、Chunk 3"
        assert topic_state.source_type == "file"
        assert topic_state.source_path == "docs/Transformer 入门.md"
        assert topic_state.material_chars == len("Transformer notes")

    def test_topic_display_title_falls_back_to_chunk_title_for_legacy_state(self):
        app = make_app()
        state = {
            "chunks": [
                {"title": "注意力机制"},
            ]
        }

        assert app._topic_display_title("topic_20260503_120000", state) == "注意力机制"

    def test_topic_display_title_falls_back_to_topic_id(self):
        app = make_app()

        assert app._topic_display_title("topic_20260503_120000", {}) == "topic_20260503_120000"
