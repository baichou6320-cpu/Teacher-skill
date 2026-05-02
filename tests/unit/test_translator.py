"""Tests for src/llm/translator.py."""

import pytest

from src.llm.translator import ResponseTranslator
from models.protocol import ResponseType


class TestParseJson:
    """Tests for ResponseTranslator.parse_json."""

    def test_empty_and_whitespace_returns_none(self):
        t = ResponseTranslator()
        assert t.parse_json("") is None
        assert t.parse_json("   ") is None
        assert t.parse_json(None) is None  # type: ignore[arg-type]

    def test_plain_json(self):
        t = ResponseTranslator()
        assert t.parse_json('{"a": 1}') == {"a": 1}

    def test_json_with_json_code_block(self):
        t = ResponseTranslator()
        text = '```json\n{"a": 1}\n```'
        assert t.parse_json(text) == {"a": 1}

    def test_json_with_generic_code_block(self):
        t = ResponseTranslator()
        text = '```\n{"a": 1}\n```'
        assert t.parse_json(text) == {"a": 1}

    def test_json_embedded_in_text(self):
        t = ResponseTranslator()
        text = 'Here is the result:\n```json\n{"a": 1}\n```\nHope that helps!'
        assert t.parse_json(text) == {"a": 1}

    def test_balanced_braces_extraction(self):
        t = ResponseTranslator()
        text = 'prefix {"nested": {"a": 1}} suffix'
        assert t.parse_json(text) == {"nested": {"a": 1}}

    def test_multiple_braces_takes_outermost(self):
        t = ResponseTranslator()
        text = 'text {"outer": {"inner": 1}} more'
        assert t.parse_json(text) == {"outer": {"inner": 1}}

    def test_unbalanced_braces_falls_back(self):
        t = ResponseTranslator()
        # unbalanced, should fall through to direct parse which also fails
        assert t.parse_json('{"a": 1') is None

    def test_invalid_json_returns_none(self):
        t = ResponseTranslator()
        assert t.parse_json("not json at all") is None

    def test_json_array_returns_dict_not_list(self):
        t = ResponseTranslator()
        # parse_json only looks for {...}, not [...]
        text = '[1, 2, 3]'
        assert t.parse_json(text) is None


class TestParseMaterialAnalysis:
    """Tests for ResponseTranslator.parse_material_analysis."""

    def test_valid_json(self):
        t = ResponseTranslator()
        resp = (
            '{"topic_title": "T", "topic_id": "tid", '
            '"chunks": [{"chunk_id": "c1", "answer": "A"}]}'
        )
        result = t.parse_material_analysis(resp)
        assert result is not None
        assert result["topic_title"] == "T"
        assert result["topic_id"] == "tid"
        assert result["chunks"][0]["correct_answer"] == "A"
        assert "answer" not in result["chunks"][0]

    def test_valid_json_already_has_correct_answer(self):
        t = ResponseTranslator()
        resp = (
            '{"topic_title": "T", "topic_id": "tid", '
            '"chunks": [{"chunk_id": "c1", "correct_answer": "B"}]}'
        )
        result = t.parse_material_analysis(resp)
        assert result["chunks"][0]["correct_answer"] == "B"

    def test_fallback_extraction(self):
        t = ResponseTranslator()
        resp = (
            '"topic_title": "T", "topic_id": "tid", '
            '"chunks": [{"chunk_id": "c1", "title": "title1"}]'
        )
        # Test the fallback directly; parse_material_analysis may
        # successfully parse a sub-object via parse_json first.
        result = t._fallback_extract_material(resp)
        assert result is not None
        assert result["topic_title"] == "T"
        assert result["topic_id"] == "tid"
        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["chunk_id"] == "c1"

    def test_unparseable_returns_none(self):
        t = ResponseTranslator()
        assert t.parse_material_analysis("no data here") is None


class TestParseJudgment:
    """Tests for ResponseTranslator.parse_judgment."""

    def test_standard_json(self):
        t = ResponseTranslator()
        resp = (
            '{"is_correct": true, "feedback": "good job", '
            '"hint_level": 1, "action": "next_chunk"}'
        )
        result = t.parse_judgment(resp)
        assert result["is_correct"] is True
        assert result["feedback"] == "good job"
        assert result["hint_level"] == 1
        assert result["action"] == "next_chunk"

    def test_standard_json_defaults(self):
        t = ResponseTranslator()
        resp = '{}'
        result = t.parse_judgment(resp)
        assert result["is_correct"] is False
        assert result["feedback"] == ""
        assert result["hint_level"] == 0
        assert result["action"] == "continue"

    def test_aimessage_format_correct(self):
        t = ResponseTranslator()
        resp = '{"response_type": "feedback_correct", "content": "nice", "hint_level": 0}'
        result = t.parse_judgment(resp)
        assert result["is_correct"] is True
        assert result["action"] == "next_chunk"
        assert result["feedback"] == "nice"

    def test_aimessage_format_wrong(self):
        t = ResponseTranslator()
        resp = '{"response_type": "feedback_wrong", "content": "oops", "hint_level": 2}'
        result = t.parse_judgment(resp)
        assert result["is_correct"] is False
        assert result["action"] == "continue"

    def test_keyword_fallback_correct(self):
        t = ResponseTranslator()
        result = t.parse_judgment("✅ 完全正确！答对了！")
        assert result["is_correct"] is True
        assert result["action"] == "next_chunk"

    def test_keyword_fallback_wrong(self):
        t = ResponseTranslator()
        result = t.parse_judgment("❌ 答错了，不太对")
        assert result["is_correct"] is False
        assert result["action"] == "continue"

    def test_keyword_fallback_next(self):
        t = ResponseTranslator()
        result = t.parse_judgment("进入下一个知识点")
        assert result["action"] == "next_chunk"

    def test_plain_text_no_signals(self):
        t = ResponseTranslator()
        result = t.parse_judgment("some random text")
        assert result["is_correct"] is False
        assert result["action"] == "continue"
        assert result["feedback"] == "some random text"


class TestToAiMessage:
    """Tests for ResponseTranslator.to_ai_message."""

    def test_from_json(self):
        t = ResponseTranslator()
        resp = (
            '{"response_type": "question", "content": "what?", '
            '"question": "Q?", "options": ["A","B"]}'
        )
        msg = t.to_ai_message(resp)
        assert msg.response_type == ResponseType.QUESTION
        assert msg.question == "Q?"
        assert msg.options == ["A", "B"]

    def test_from_json_unknown_response_type(self):
        t = ResponseTranslator()
        resp = '{"response_type": "unknown_type", "content": "hi"}'
        msg = t.to_ai_message(resp)
        assert msg.response_type == ResponseType.EXPLANATION

    def test_from_text_question(self):
        t = ResponseTranslator()
        msg = t.to_ai_message("What is this: A or B?")
        assert msg.response_type == ResponseType.QUESTION

    def test_from_text_correct(self):
        t = ResponseTranslator()
        msg = t.to_ai_message("✅ 答对了")
        assert msg.response_type == ResponseType.FEEDBACK_CORRECT

    def test_from_text_wrong(self):
        t = ResponseTranslator()
        msg = t.to_ai_message("❌ 答错了")
        assert msg.response_type == ResponseType.FEEDBACK_WRONG

    def test_from_text_hint(self):
        t = ResponseTranslator()
        msg = t.to_ai_message("💡 提示：想想看")
        assert msg.response_type == ResponseType.FEEDBACK_HINT

    def test_from_text_direct_answer(self):
        t = ResponseTranslator()
        msg = t.to_ai_message("/direct 速查直接给答案")
        assert msg.response_type == ResponseType.DIRECT_ANSWER

    def test_from_text_explanation(self):
        t = ResponseTranslator()
        msg = t.to_ai_message("This is an explanation.")
        assert msg.response_type == ResponseType.EXPLANATION

    def test_empty_text(self):
        t = ResponseTranslator()
        msg = t.to_ai_message("")
        assert msg.content == "（模型未返回有效内容）"
        assert msg.response_type == ResponseType.EXPLANATION
