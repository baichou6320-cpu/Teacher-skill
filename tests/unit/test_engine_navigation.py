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

    def add_user_message(self, content: str, answer=None) -> None:
        self.user_messages.append(content)


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
