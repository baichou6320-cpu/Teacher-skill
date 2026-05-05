"""Tests for TutorEngine navigation helpers."""

import pytest

from models.protocol import AIMessage, ResponseType
from models.state import ChunkState, LearningStatus, TopicState
from src.core.engine import TutorEngine, TutorState


class DummyLogger:
    """Logger stub used by engine tests."""

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class FakeMemory:
    """Memory stub used by engine tests."""

    def __init__(self):
        self.user_messages: list[str] = []
        self.ai_messages: list[AIMessage] = []

    def add_user_message(self, content: str, answer=None) -> None:
        self.user_messages.append(content)

    def add_ai_message(self, message: AIMessage) -> None:
        self.ai_messages.append(message)

    def get_context_for_llm(self, count: int = 5) -> str:
        return ""


def make_topic_state(current_index: int = 0) -> TopicState:
    """Create a three-chunk topic for navigation tests."""
    return TopicState(
        topic_id="topic_test",
        user_id="user_test",
        current_chunk_index=current_index,
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


def make_engine(topic_state: TopicState) -> TutorEngine:
    """Create a TutorEngine instance without initializing the LLM client."""
    engine = TutorEngine.__new__(TutorEngine)
    engine.user_id = "user_test"
    engine.topic_id = topic_state.topic_id
    engine.state = TutorState.WAITING_ANSWER
    engine.topic_state = topic_state
    engine._review_mode = False
    engine._review_queue = []
    engine._review_position = 0
    engine.memory = FakeMemory()
    engine.logger = DummyLogger()

    def fake_teach_current_chunk() -> AIMessage:
        chunk = engine.topic_state.chunks[engine.topic_state.current_chunk_index]
        return AIMessage(
            response_type=ResponseType.QUESTION,
            content=f"teach {chunk.title}",
            question=chunk.question,
            chunk_id=chunk.chunk_id,
        )

    engine._teach_current_chunk = fake_teach_current_chunk
    return engine


def test_skip_marks_current_chunk_needs_review_and_advances():
    topic_state = make_topic_state()
    engine = make_engine(topic_state)

    response = engine.skip_current_chunk()

    assert topic_state.chunks[0].status == LearningStatus.NEEDS_REVIEW
    assert topic_state.current_chunk_index == 1
    assert response.response_type == ResponseType.QUESTION
    assert engine.memory.user_messages == ["/skip"]


def test_back_moves_to_previous_chunk():
    topic_state = make_topic_state(current_index=2)
    engine = make_engine(topic_state)

    response = engine.previous_chunk()

    assert topic_state.current_chunk_index == 1
    assert topic_state.is_completed is False
    assert response.chunk_id == "chunk_2"
    assert engine.memory.user_messages == ["/back"]


def test_back_at_first_chunk_does_not_move():
    topic_state = make_topic_state(current_index=0)
    engine = make_engine(topic_state)

    response = engine.previous_chunk()

    assert topic_state.current_chunk_index == 0
    assert response.response_type == ResponseType.EXPLANATION


def test_jump_moves_to_requested_chunk():
    topic_state = make_topic_state()
    engine = make_engine(topic_state)

    response = engine.jump_to_chunk(3)

    assert topic_state.current_chunk_index == 2
    assert topic_state.is_completed is False
    assert response.chunk_id == "chunk_3"
    assert engine.memory.user_messages == ["/jump 3"]


def test_jump_rejects_out_of_range_chunk():
    topic_state = make_topic_state()
    engine = make_engine(topic_state)

    with pytest.raises(ValueError):
        engine.jump_to_chunk(4)


def test_analyze_material_saves_readable_topic_metadata():
    engine = TutorEngine.__new__(TutorEngine)
    engine.user_id = "user_test"
    engine.topic_id = "topic_test"
    engine.state = TutorState.IDLE
    engine.logger = DummyLogger()

    def fake_analysis(material: str, user_level: str) -> dict:
        return {
            "topic_title": "Transformer 入门",
            "summary": "理解注意力机制和编码器结构",
            "chunks": [
                {
                    "chunk_id": "chunk_1",
                    "title": "注意力机制",
                    "content": "content",
                    "question": "question?",
                    "correct_answer": "answer",
                }
            ],
        }

    engine._request_material_analysis = fake_analysis

    topic_state = engine.analyze_material("material text", user_level="beginner")

    assert topic_state.title == "Transformer 入门"
    assert topic_state.summary == "理解注意力机制和编码器结构"
    assert topic_state.material_chars == len("material text")
    assert topic_state.total_chunks == 1


def test_start_review_prioritizes_weak_chunks_without_teaching():
    topic_state = make_topic_state()
    topic_state.chunks[0].status = LearningStatus.MASTERED
    topic_state.chunks[1].status = LearningStatus.NEEDS_REVIEW
    topic_state.chunks[2].fail_count = 1
    engine = make_engine(topic_state)

    response = engine.start_review(topic_state)

    assert engine._review_queue == [1, 2, 0]
    assert topic_state.current_chunk_index == 1
    assert response.response_type == ResponseType.QUESTION
    assert response.question == "Question 2?"
    assert response.content.startswith("复习模式")
    assert engine.get_review_progress() == "1/3"


def test_next_review_chunk_advances_without_calling_teach():
    topic_state = make_topic_state()
    topic_state.chunks[0].status = LearningStatus.NEEDS_REVIEW
    engine = make_engine(topic_state)
    engine.start_review(topic_state)

    response = engine.next_review_chunk()

    assert response.response_type == ResponseType.QUESTION
    assert topic_state.current_chunk_index == 1
    assert response.question == "Question 2?"


def test_skip_review_chunk_marks_needs_review_and_completes_queue():
    topic_state = make_topic_state()
    topic_state.chunks = topic_state.chunks[:1]
    topic_state.total_chunks = 1
    engine = make_engine(topic_state)
    engine.start_review(topic_state)

    response = engine.skip_review_chunk()

    assert topic_state.chunks[0].status == LearningStatus.NEEDS_REVIEW
    assert response.is_final is True
    assert engine._review_mode is False


def test_review_answer_uses_review_prompt_for_judgment():
    topic_state = make_topic_state()
    topic_state.chunks[0].status = LearningStatus.NEEDS_REVIEW
    engine = make_engine(topic_state)
    engine.start_review(topic_state)

    prompts_used: list[str] = []
    engine._get_system_prompt = lambda module: module

    def fake_call_llm(system_prompt: str, user_message: str, max_tokens=None) -> str:
        prompts_used.append(system_prompt)
        assert "复习模式" in user_message
        return "{}"

    class FakeTranslator:
        def parse_judgment(self, response: str) -> dict:
            return {
                "is_correct": False,
                "feedback": "短提示",
                "hint_level": 1,
                "action": "continue",
            }

    engine._call_llm = fake_call_llm
    engine.translator = FakeTranslator()

    response = engine.receive_answer("不确定", is_direct=False)

    assert prompts_used == ["review"]
    assert response.response_type == ResponseType.FEEDBACK_WRONG
    assert response.content == "短提示"
