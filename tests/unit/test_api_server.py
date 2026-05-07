"""Tests for the local web/API bridge."""

from api_server import (
    _resolve_static_file,
    analyze_payload,
    hint_payload,
    judge_payload,
    respond_payload,
    teach_payload,
    web_demo_payload,
)


def test_resolve_static_file_serves_index(tmp_path):
    web_root = tmp_path / "web"
    web_root.mkdir()
    index_file = web_root / "index.html"
    index_file.write_text("<h1>Teacher-skill</h1>", encoding="utf-8")

    assert _resolve_static_file(web_root, "/") == index_file


def test_resolve_static_file_blocks_path_traversal(tmp_path):
    web_root = tmp_path / "web"
    web_root.mkdir()
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")

    assert _resolve_static_file(web_root, "/../secret.txt") is None


def test_analyze_payload_can_run_without_real_engine():
    result = analyze_payload(
        {
            "text": "主动回忆可以避免把熟悉感误认为真正掌握。",
            "fileName": "notes.txt",
            "userLevel": "beginner",
            "useRealEngine": False,
        }
    )

    assert result["ok"] is True
    assert result["source"] == "local_fallback"
    assert result["file"]["name"] == "notes.txt"
    assert result["concepts"]
    assert result["questions"]


def test_web_demo_payload_is_fixed_recording_flow():
    result = web_demo_payload()

    assert result["ok"] is True
    assert result["mode"] == "recording_demo"
    assert result["material"]
    assert result["goal"]
    assert len(result["cards"]) == 3
    assert result["cards"][0]["title"] == "番茄工作法"


def test_teach_payload_can_run_without_real_engine():
    result = teach_payload(
        {
            "useRealEngine": False,
            "learningGoal": "理解主动回忆",
            "card": {
                "id": "chunk_1",
                "title": "主动回忆",
                "content": "主动回忆要求学习者在不看答案的情况下输出理解。",
                "question": "为什么主动回忆比只看答案更能检验掌握？",
                "answer": "因为它能暴露你是否真的能独立提取知识。",
            },
        }
    )

    assert result["ok"] is True
    assert result["source"] == "local_fallback"
    assert "主动回忆" in result["content"]
    assert result["question"]


def test_teach_payload_progressive_explain_is_not_judgment():
    result = teach_payload(
        {
            "useRealEngine": False,
            "userRequest": "我不理解，直接详细解释一下",
            "supportMode": "progressive_explain",
            "learningGoal": "理解主动回忆",
            "card": {
                "id": "chunk_1",
                "title": "主动回忆",
                "content": "主动回忆要求学习者在不看答案的情况下输出理解。",
                "question": "为什么主动回忆比只看答案更能检验掌握？",
                "answer": "因为它能暴露你是否真的能独立提取知识。",
            },
        }
    )

    assert result["ok"] is True
    assert result["responseType"] == "question"
    assert "不判卷" in result["content"]
    assert "渐进讲解" in result["content"]
    assert result["question"].startswith("轻量确认")


def test_respond_payload_routes_answer_with_what_is_phrase_to_judge():
    result = respond_payload(
        {
            "useRealEngine": False,
            "userInput": "XGBoost 是什么，类似于由多棵树组成的集成学习方法。",
            "card": {
                "id": "chunk_1",
                "title": "XGBoost",
                "content": "XGBoost 是一种基于梯度提升树的集成学习方法。",
                "question": "请用自己的话解释 XGBoost 在材料里的作用。",
                "answer": "它通过组合多棵弱学习树来提升预测效果。",
            },
        }
    )

    assert result["ok"] is True
    assert result["intent"] == "answer"
    assert result["classifierSource"] == "local_router"
    assert "判卷" in result["content"] or result["responseType"] in {"feedback_correct", "feedback_hint"}


def test_respond_payload_routes_explain_request_to_progressive_teach():
    result = respond_payload(
        {
            "useRealEngine": False,
            "userInput": "我不太懂，能一步步解释一下 XGBoost 是什么",
            "card": {
                "id": "chunk_1",
                "title": "XGBoost",
                "content": "XGBoost 是一种基于梯度提升树的集成学习方法。",
                "question": "请用自己的话解释 XGBoost 在材料里的作用。",
                "answer": "它通过组合多棵弱学习树来提升预测效果。",
            },
        }
    )

    assert result["ok"] is True
    assert result["intent"] == "explain"
    assert result["classifierSource"] == "local_router"
    assert "渐进讲解" in result["content"]


def test_respond_payload_routes_direct_explain_without_follow_up_question():
    result = respond_payload(
        {
            "useRealEngine": False,
            "userInput": "不太能，可以直接跟我说这个概念。",
            "learningGoal": "理解 XGBoost",
            "card": {
                "id": "chunk_1",
                "title": "XGBoost",
                "content": "XGBoost 是一种基于梯度提升树的集成学习方法。",
                "question": "请用自己的话解释 XGBoost 在材料里的作用。",
                "answer": "它通过组合多棵弱学习树来提升预测效果。",
            },
        }
    )

    assert result["ok"] is True
    assert result["intent"] == "explain"
    assert result["askFollowUp"] is False
    assert result["question"] is None
    assert "直接把" in result["content"]


def test_judge_payload_can_run_without_real_engine():
    result = judge_payload(
        {
            "useRealEngine": False,
            "answer": "主动回忆能让人不看答案也说出核心内容，所以能检验是否真的掌握。",
            "card": {
                "title": "主动回忆",
                "content": "主动回忆要求学习者在不看答案的情况下输出理解。",
                "question": "为什么主动回忆比只看答案更能检验掌握？",
                "answer": "因为它能暴露你是否真的能独立提取知识。",
            },
        }
    )

    assert result["ok"] is True
    assert result["source"] == "local_fallback"
    assert result["isCorrect"] is True
    assert result["status"] == "mastered"


def test_hint_payload_can_run_without_real_engine():
    result = hint_payload(
        {
            "useRealEngine": False,
            "hintLevel": 0,
            "card": {
                "title": "主动回忆",
                "content": "主动回忆要求学习者在不看答案的情况下输出理解。",
                "question": "为什么主动回忆比只看答案更能检验掌握？",
                "answer": "因为它能暴露你是否真的能独立提取知识。",
            },
        }
    )

    assert result["ok"] is True
    assert result["source"] == "local_fallback"
    assert result["hintLevel"] == 1
    assert "提示" in result["content"]
