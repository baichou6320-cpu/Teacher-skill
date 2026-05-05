"""Tests for natural-language intent routing helpers."""

from models.user import LearnedTopic
from src.core.router import extract_review_query, is_review_intent, match_history_topic


def test_is_review_intent_supports_chinese_and_english():
    assert is_review_intent("复习一下 transformer")
    assert is_review_intent("review transformer notes")
    assert not is_review_intent("学习一篇新文章")


def test_extract_review_query_removes_common_fillers():
    assert extract_review_query("帮我复习一下之前学过的 Transformer") == "Transformer"


def test_match_history_topic_by_title():
    topics = [
        LearnedTopic(topic_id="topic_1", title="番茄工作法入门"),
        LearnedTopic(topic_id="topic_2", title="Transformer 自注意力机制"),
    ]

    matched = match_history_topic("复习一下 transformer", topics)

    assert matched is topics[1]


def test_match_history_topic_by_summary_or_source_path():
    topics = [
        LearnedTopic(
            topic_id="topic_1",
            title="学习方法",
            summary="关于专注周期和休息节奏",
            source_path="notes/pomodoro.md",
        )
    ]

    assert match_history_topic("回顾一下专注周期", topics) is topics[0]
    assert match_history_topic("review pomodoro", topics) is topics[0]


def test_match_history_topic_returns_none_when_score_is_weak():
    topics = [LearnedTopic(topic_id="topic_1", title="番茄工作法入门")]

    assert match_history_topic("复习一下 transformer", topics) is None
