"""Intent routing helpers for CLI commands and natural-language requests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


REVIEW_KEYWORDS = (
    "复习",
    "回顾",
    "温习",
    "再看一遍",
    "再学一遍",
    "巩固",
    "review",
    "recap",
    "revisit",
)

_REVIEW_FILLERS = (
    "一下",
    "帮我",
    "我想",
    "之前",
    "以前",
    "学过的",
    "学的",
    "学习过的",
    "内容",
    "主题",
    "the",
    "a",
    "an",
    "please",
)


def is_review_intent(text: str) -> bool:
    """Return whether a free-form user input asks for review."""
    normalized = _normalize_text(text)
    return any(_normalize_text(keyword) in normalized for keyword in REVIEW_KEYWORDS)


def extract_review_query(text: str) -> str:
    """Remove common review intent words and keep the topic query part."""
    query = text.strip()
    for keyword in (*REVIEW_KEYWORDS, *_REVIEW_FILLERS):
        if keyword.isascii() and keyword.isalpha():
            query = re.sub(rf"\b{re.escape(keyword)}\b", " ", query, flags=re.IGNORECASE)
        else:
            query = re.sub(re.escape(keyword), " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" ，。,.!！?？")
    return query


def match_history_topic(text: str, history_topics: Iterable[Any]) -> Any | None:
    """Find the best matching learned topic for a review request.

    The matcher is intentionally simple and deterministic: it checks title,
    summary, source filename, and topic_id. This is enough for the first review
    mode iteration and avoids spending an LLM call before the user enters review.
    """
    query = extract_review_query(text) if is_review_intent(text) else text.strip()
    query_norm = _normalize_text(query)
    query_tokens = _query_tokens(query)
    if not query_norm and not query_tokens:
        return None

    best_topic = None
    best_score = 0
    for topic in history_topics:
        score = _score_topic(query_norm, query_tokens, topic)
        if score > best_score:
            best_score = score
            best_topic = topic

    return best_topic if best_score >= 20 else None


def _score_topic(query_norm: str, query_tokens: list[str], topic: Any) -> int:
    """Score one topic against the user's query."""
    score = 0
    for field in _topic_search_fields(topic):
        field_norm = _normalize_text(field)
        if not field_norm:
            continue

        if query_norm and query_norm == field_norm:
            score += 100
        elif query_norm and query_norm in field_norm:
            score += 70
        elif query_norm and field_norm in query_norm:
            score += 40

        for token in query_tokens:
            if token and token in field_norm:
                score += 25 if len(token) >= 2 else 5

    return score


def _topic_search_fields(topic: Any) -> list[str]:
    """Return searchable strings from a LearnedTopic-like object or dict."""
    title = _topic_value(topic, "title")
    summary = _topic_value(topic, "summary")
    source_path = _topic_value(topic, "source_path")
    topic_id = _topic_value(topic, "topic_id")
    source_name = Path(source_path).stem if source_path else ""
    return [title, summary, source_path, source_name, topic_id]


def _topic_value(topic: Any, key: str) -> str:
    if isinstance(topic, dict):
        value = topic.get(key, "")
    else:
        value = getattr(topic, key, "")
    return str(value or "")


def _query_tokens(text: str) -> list[str]:
    """Split query into useful searchable tokens."""
    text = extract_review_query(text)
    tokens = re.findall(r"[a-zA-Z0-9_+-]+|[\u4e00-\u9fff]{2,}", text.lower())
    return [token for token in tokens if token and token not in _REVIEW_FILLERS]


def _normalize_text(text: str) -> str:
    """Normalize text for rough matching across Chinese and English names."""
    return re.sub(r"[\s\-_/\\:：,.，。!！?？()（）\[\]【】]+", "", text.lower())
