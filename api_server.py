"""Local HTTP bridge for the figma1 React prototype.

This server intentionally uses only the Python standard library plus the
project's existing runtime dependencies. It accepts PDF/txt/md uploads from the
frontend, extracts text through ``src.utils.file_loader``, and then tries to run
Teacher-skill's real ``TutorEngine.analyze_material`` flow.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

from models.protocol import AIMessage, ResponseType
from models.state import ChunkState, LearningStatus, TopicState
from src.core.engine import TutorEngine
from src.utils.config import get_config
from src.utils.file_loader import load_file


PROJECT_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = PROJECT_ROOT / ".tmp" / "figma1_uploads"
SHOWCASE_DIR = PROJECT_ROOT / "showcase"
REACT_DIST_DIR = PROJECT_ROOT / "figma1" / "dist"
HOST = "127.0.0.1"
PORT = 8765
WEB_DEMO_MATERIAL_PATH = PROJECT_ROOT / "samples" / "demo_article.md"

load_dotenv(PROJECT_ROOT / ".env")


KEYWORD_BANK = [
    {
        "label": "模型对齐",
        "aliases": ["alignment", "对齐", "人类意图", "安全训练"],
        "question": "如果模型完成了字面指令，但违背了真实学习目标，这算不算对齐失败？为什么？",
        "alert": "容易把“听话”误认为“对齐”，忽略边界和长期影响。",
    },
    {
        "label": "越狱",
        "aliases": ["jailbreak", "越狱", "绕过", "安全策略"],
        "question": "为什么模型经过安全训练后，仍然可能被特殊措辞诱导输出不合适内容？",
        "alert": "容易只记住攻击话术，而没有理解它在绕过哪一层约束。",
    },
    {
        "label": "提示注入",
        "aliases": ["prompt injection", "提示注入", "外部材料", "网页", "文档"],
        "question": "提示注入和越狱最大的区别是什么？它为什么对 Agent 工具调用更危险？",
        "alert": "容易把提示注入当作普通用户提问，忽略它来自被读取的外部内容。",
    },
    {
        "label": "自注意力",
        "aliases": ["self-attention", "自注意力", "注意力机制", "token", "序列关系"],
        "question": "自注意力为什么能帮助模型理解不同 token 之间的关系？",
        "alert": "容易只记公式，不清楚它到底在比较哪些信息。",
    },
    {
        "label": "主动回忆",
        "aliases": ["主动回忆", "闭卷", "复述", "复习", "错题", "薄弱点"],
        "question": "为什么只看答案不等于真正理解？你会如何验证自己真的掌握？",
        "alert": "容易把熟悉感当成掌握，缺少闭卷输出检验。",
    },
]


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def _select_web_root() -> Path:
    """Prefer a built React app, otherwise serve the no-build local showcase."""
    if (REACT_DIST_DIR / "index.html").is_file():
        return REACT_DIST_DIR
    return SHOWCASE_DIR


def _resolve_static_file(web_root: Path, request_path: str) -> Path | None:
    """Resolve one local web asset while blocking path traversal."""
    root = web_root.resolve()
    parsed_path = unquote(urlparse(request_path).path)
    relative = parsed_path.lstrip("/") or "index.html"
    candidate = (root / relative).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        return None

    if candidate.is_dir():
        candidate = candidate / "index.html"

    if candidate.is_file():
        return candidate

    # Built Vite apps need SPA fallback for client-side routes.
    index_file = root / "index.html"
    if root == REACT_DIST_DIR.resolve() and index_file.is_file():
        return index_file

    return None


def _static_response(handler: BaseHTTPRequestHandler, path: Path) -> None:
    body = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix.lower() in {".html", ".css", ".js"}:
        content_type = f"{content_type}; charset=utf-8"

    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fa5]", "_", name).strip("._")
    return cleaned or "material.txt"


def _split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[。！？.!?]\s*", re.sub(r"\s+", " ", text)) if item.strip()]


def _summary(text: str) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return "材料为空，无法生成摘要。"
    return "。".join(sentences[:2]) + ("。" if len(sentences) > 1 else "")


def _fallback_analysis(material: str, file_name: str, reason: str) -> dict[str, Any]:
    lowered = material.lower()
    concepts = [
        {**item, "source": "本地规则 fallback"}
        for item in KEYWORD_BANK
        if any(alias.lower() in lowered for alias in item["aliases"])
    ]
    if not concepts:
        words = [
            word
            for word in re.split(r"\s+", re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9\s]", " ", material))
            if len(word) >= 2
        ]
        unique_words = list(dict.fromkeys(words))[:5] or ["核心主题"]
        concepts = [
            {
                "label": word,
                "source": "本地规则 fallback",
                "question": f"请用自己的话解释“{word}”在材料里的作用。",
                "alert": f"需要确认“{word}”的定义、例子和边界。",
            }
            for word in unique_words
        ]

    return {
        "ok": True,
        "source": "local_fallback",
        "fallbackReason": reason,
        "title": Path(file_name).stem or "本地材料分析",
        "summary": _summary(material),
        "stats": {
            "chars": len(material),
            "paragraphs": len([p for p in material.splitlines() if p.strip()]),
            "sentences": len(_split_sentences(material)),
        },
        "concepts": [
            {"label": item["label"], "source": item["source"], "content": ""}
            for item in concepts[:5]
        ],
        "questions": [item["question"] for item in concepts[:3]],
        "alerts": [item["alert"] for item in concepts[:3]],
        "needsReview": [f"用自己的话解释“{item['label']}”，并举一个反例。" for item in concepts[:3]],
        "reviewPlan": [
            "明天 09:30：闭卷写出 3 个核心概念的定义和边界。",
            "明天 14:00：回答追问，只允许看自己的草稿。",
            "明天 20:00：把薄弱点整理成复习卡片。",
        ],
        "chunks": [],
    }


def _topic_to_payload(topic: TopicState, material: str, file_name: str) -> dict[str, Any]:
    chunks = [
        {
            "id": chunk.chunk_id,
            "title": chunk.title,
            "content": chunk.content,
            "question": chunk.question,
            "answer": chunk.correct_answer,
            "difficulty": chunk.difficulty,
        }
        for chunk in topic.chunks
    ]
    concepts = [
        {
            "label": chunk.title or f"知识点 {index + 1}",
            "source": "Teacher-skill LLM",
            "content": chunk.content,
        }
        for index, chunk in enumerate(topic.chunks)
    ]
    questions = [chunk.question for chunk in topic.chunks if chunk.question]
    needs_review = [
        f"复习“{chunk.title or f'知识点 {index + 1}'}”：先闭卷回答，再查看正确答案。"
        for index, chunk in enumerate(topic.chunks[:3])
    ]

    return {
        "ok": True,
        "source": "teacher_skill_llm",
        "fallbackReason": "",
        "title": topic.title or Path(file_name).stem or "Teacher-skill 分析结果",
        "summary": topic.summary or _summary(material),
        "stats": {
            "chars": len(material),
            "paragraphs": len([p for p in material.splitlines() if p.strip()]),
            "sentences": len(_split_sentences(material)),
        },
        "concepts": concepts[:6],
        "questions": questions[:5],
        "alerts": [
            "真实 Agent 已完成材料拆解；建议继续进入问答判卷闭环。",
            "如果概念过多，先挑 3 个高优先级知识点做主动回忆。",
        ],
        "needsReview": needs_review or ["从第一个知识点开始闭卷回答验证问题。"],
        "reviewPlan": [
            "今天：完成第一个知识点的主动回忆。",
            "明天：复习所有未掌握知识点并回答验证问题。",
            "三天后：重新抽查易错概念，确认没有只记住答案。",
        ],
        "chunks": chunks,
    }


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _card_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    card = payload.get("card")
    if isinstance(card, dict):
        return card
    return payload


def _chunk_from_card(card: dict[str, Any]) -> ChunkState:
    title = _first_text(card.get("title"), card.get("label"), default="当前知识点")
    content = _first_text(
        card.get("content"),
        card.get("answer"),
        card.get("correctAnswer"),
        card.get("correct_answer"),
        default=f"{title} 是当前资料里的一个关键概念，需要理解它的定义、作用和边界。",
    )
    question = _first_text(
        card.get("question"),
        default=f"请用自己的话解释“{title}”在材料里的作用。",
    )
    correct_answer = _first_text(
        card.get("correct_answer"),
        card.get("correctAnswer"),
        card.get("answer"),
        card.get("content"),
        default=content,
    )
    options = card.get("options")
    if not isinstance(options, list):
        options = None

    status_text = _first_text(card.get("statusValue"), card.get("status"), default="not_started")
    status_map = {
        "已掌握": LearningStatus.MASTERED,
        "待巩固": LearningStatus.NEEDS_REVIEW,
        "学习中": LearningStatus.IN_PROGRESS,
        "未开始": LearningStatus.NOT_STARTED,
        "mastered": LearningStatus.MASTERED,
        "needs_review": LearningStatus.NEEDS_REVIEW,
        "in_progress": LearningStatus.IN_PROGRESS,
        "not_started": LearningStatus.NOT_STARTED,
    }

    return ChunkState(
        chunk_id=_first_text(card.get("id"), card.get("chunk_id"), default=f"web_chunk_{uuid.uuid4().hex[:8]}"),
        title=title,
        content=content,
        question=question,
        options=options,
        correct_answer=correct_answer,
        analogy=_first_text(card.get("analogy"), default=""),
        difficulty=_first_text(card.get("difficulty"), default="medium"),
        status=status_map.get(status_text, LearningStatus.NOT_STARTED),
        fail_count=_int_value(card.get("failCount", card.get("fail_count")), 0),
        hint_level=_int_value(card.get("hintLevel", card.get("hint_level")), 0),
        attempts=_int_value(card.get("attempts"), 0),
    )


def _topic_from_card_payload(payload: dict[str, Any]) -> tuple[TopicState, ChunkState]:
    card = _card_from_payload(payload)
    chunk = _chunk_from_card(card)
    topic = TopicState(
        topic_id=f"web_topic_{uuid.uuid4().hex[:8]}",
        user_id="web_user",
        title=_first_text(payload.get("learningGoal"), card.get("title"), default="网页学习主题"),
        summary=_first_text(payload.get("learningGoal"), default="本地网页学习会话"),
        current_chunk_index=0,
        total_chunks=1,
        chunks=[chunk],
    )
    return topic, chunk


def _message_payload(
    message: AIMessage,
    *,
    source: str,
    fallback_reason: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response_type = getattr(message.response_type, "value", str(message.response_type))
    payload: dict[str, Any] = {
        "ok": True,
        "source": source,
        "fallbackReason": fallback_reason,
        "responseType": response_type,
        "content": message.content,
        "question": message.question,
        "options": message.options,
        "correctAnswer": message.correct_answer,
        "hintLevel": message.hint_level,
        "isFinal": message.is_final,
    }
    if extra:
        payload.update(extra)
    return payload


def _run_with_timeout(action: Callable[[], Any], timeout: int = 18) -> Any:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(action)
    try:
        return future.result(timeout=timeout)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _fallback_teach(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    card = _card_from_payload(payload)
    chunk = _chunk_from_card(card)
    goal = _first_text(payload.get("learningGoal"), default="理解这个知识点")
    style = _first_text(payload.get("learningStyle"), default="苏格拉底")
    user_request = _first_text(payload.get("userRequest"))
    support_mode = _first_text(payload.get("supportMode"))
    ask_follow_up = True
    response_type = ResponseType.QUESTION
    if support_mode == "direct_explain":
        content = (
            f"可以，我先直接把“{chunk.title}”讲清楚。\n\n"
            f"1. 它是什么：{chunk.content}\n\n"
            f"2. 它解决什么问题：它帮助你理解“{goal}”里最关键的关系，而不是只记住一个名词。\n\n"
            f"3. 可以怎么类比：{chunk.analogy or f'可以把“{chunk.title}”看成一个把零散材料组织起来的抓手。'}\n\n"
            f"4. 容易混淆的边界：不要只回答“它叫什么”，还要说出它为什么有用、适合什么场景，以及和相近概念有什么区别。\n\n"
            f"一句话记忆：{chunk.correct_answer or chunk.content}"
        )
        question = None
        ask_follow_up = False
        response_type = ResponseType.EXPLANATION
    elif support_mode == "progressive_explain" or user_request:
        content = (
            f"可以，我们先不判卷，直接进入渐进讲解。\n\n"
            f"1. 先给定义：{chunk.title} 可以理解为：{chunk.content}\n\n"
            f"2. 再看作用：它在这份资料里主要帮助你抓住“{goal}”里的关键关系。\n\n"
            f"3. 再看边界：不要只背名字，要能说出它解决什么问题、适合什么场景、和相近概念有什么区别。\n\n"
            f"4. 最后用一句话收束：{chunk.correct_answer or chunk.content}"
        )
        question = f"轻量确认：现在你能不能用一句话说出“{chunk.title}”是什么？"
    else:
        content = (
            f"围绕“{goal}”，我们先看“{chunk.title}”。"
            f"{chunk.content}\n\n"
            f"用“{style}”风格学习时，你先不用背答案，先说清楚："
            "它是什么、解决什么问题、和相近概念有什么边界。"
        )
        question = chunk.question
    message = AIMessage(
        response_type=response_type,
        content=content,
        question=question,
        options=chunk.options,
        correct_answer=chunk.correct_answer,
        chunk_id=chunk.chunk_id,
    )
    return _message_payload(
        message,
        source="local_fallback",
        fallback_reason=reason,
        extra={
            "askFollowUp": ask_follow_up,
            "card": {"hintLevel": chunk.hint_level, "failCount": chunk.fail_count, "attempts": chunk.attempts},
        },
    )


def _keywords(text: str) -> list[str]:
    words = [
        word
        for word in re.split(r"\s+", re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9\s]", " ", text))
        if len(word) >= 2
    ]
    return list(dict.fromkeys(words))[:8]


def _fallback_judge(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    _topic, chunk = _topic_from_card_payload(payload)
    answer = _first_text(payload.get("answer"), payload.get("userAnswer"))
    normalized_answer = answer.lower()
    expected_text = " ".join([chunk.title, chunk.content, chunk.correct_answer]).lower()
    expected_keywords = [word.lower() for word in _keywords(expected_text)]
    hits = [word for word in expected_keywords if word in normalized_answer]
    is_unknown = any(word in normalized_answer for word in ["不知道", "不会", "不清楚", "没懂"])
    is_correct = len(answer) >= 8 and not is_unknown and (len(hits) >= 1 or chunk.title.lower() in normalized_answer)

    if is_correct:
        chunk.status = LearningStatus.MASTERED
        message = AIMessage(
            response_type=ResponseType.FEEDBACK_CORRECT,
            content=f"方向是对的。你已经抓住了“{chunk.title}”的核心，可以再补一个例子来确认边界。",
            chunk_id=chunk.chunk_id,
        )
        return _message_payload(
            message,
            source="local_fallback",
            fallback_reason=reason,
            extra={"isCorrect": True, "action": "next_chunk", "status": "mastered"},
        )

    next_hint_level = min(chunk.hint_level + 1, 4)
    chunk.fail_count += 1
    chunk.hint_level = next_hint_level
    message = AIMessage(
        response_type=ResponseType.FEEDBACK_HINT,
        content=_fallback_hint_text(chunk, next_hint_level, direct=False),
        hint_level=next_hint_level,
        chunk_id=chunk.chunk_id,
    )
    return _message_payload(
        message,
        source="local_fallback",
        fallback_reason=reason,
        extra={
            "isCorrect": False,
            "action": "continue" if next_hint_level < 4 else "next_chunk",
            "status": "needs_review" if next_hint_level >= 4 else "in_progress",
            "card": {
                "hintLevel": chunk.hint_level,
                "failCount": chunk.fail_count,
                "attempts": chunk.attempts + 1,
            },
        },
    )


def _fallback_hint_text(chunk: ChunkState, hint_level: int, *, direct: bool) -> str:
    if direct:
        return (
            f"参考答案：{chunk.correct_answer or chunk.content}\n\n"
            "这张卡片会进入待巩固。建议之后再闭卷回答一次，而不是只停留在看懂答案。"
        )
    if hint_level <= 1:
        return f"第 1 层提示：先抓住关键词“{chunk.title}”。你可以从它解决了什么问题开始回答。"
    if hint_level == 2:
        analogy = chunk.analogy or f"可以把“{chunk.title}”想成一个帮助你组织材料理解顺序的抓手。"
        return f"第 2 层提示：试试这个类比：{analogy}"
    if hint_level == 3:
        return f"第 3 层提示：它的大意是：{chunk.content}。现在请你补一句“所以它的作用是……”。"
    return f"第 4 层提示：核心答案接近：{chunk.correct_answer or chunk.content}。请你用自己的话重新组织一遍。"


def _fallback_hint(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    _topic, chunk = _topic_from_card_payload(payload)
    direct = bool(payload.get("direct", False))
    requested_level = _int_value(payload.get("hintLevel"), chunk.hint_level)
    hint_level = 4 if direct else min(max(requested_level + 1, 1), 4)
    chunk.hint_level = hint_level
    if direct:
        chunk.status = LearningStatus.NEEDS_REVIEW
    message = AIMessage(
        response_type=ResponseType.DIRECT_ANSWER if direct else ResponseType.FEEDBACK_HINT,
        content=_fallback_hint_text(chunk, hint_level, direct=direct),
        hint_level=hint_level,
        chunk_id=chunk.chunk_id,
        is_final=direct,
    )
    return _message_payload(
        message,
        source="local_fallback",
        fallback_reason=reason,
        extra={
            "isCorrect": False,
            "action": "next_chunk" if direct or hint_level >= 4 else "continue",
            "status": "needs_review" if direct or hint_level >= 4 else "in_progress",
            "card": {"hintLevel": chunk.hint_level, "failCount": chunk.fail_count, "attempts": chunk.attempts},
        },
    )


def _real_teach_payload(payload: dict[str, Any]) -> dict[str, Any]:
    topic, chunk = _topic_from_card_payload(payload)
    engine = TutorEngine(user_id="web_user", topic_id=topic.topic_id)
    user_request = _first_text(payload.get("userRequest"))
    support_mode = _first_text(payload.get("supportMode"))
    if support_mode == "direct_explain":
        user_msg = (
            f"用户现在明确说自己暂时答不上来，希望你直接讲清楚：{user_request or '请直接解释这个知识点'}\n\n"
            "请进入直接讲解模式：不要判卷，不要说用户答错，不要在结尾追问验证问题。\n"
            "输出结构：\n"
            "1. 这个概念是什么\n"
            "2. 它解决什么问题\n"
            "3. 用一个生活化类比解释\n"
            "4. 它容易和什么混淆，边界在哪里\n"
            "5. 用一句话总结\n\n"
            f"=== 学习目标 ===\n{topic.title}\n\n"
            f"=== 知识点标题 ===\n{chunk.title}\n\n"
            f"=== 知识点内容 ===\n{chunk.content}\n\n"
            f"=== 参考答案 ===\n{chunk.correct_answer}"
        )
        response = engine._call_llm(engine._get_system_prompt("teach"), user_msg)
        message = engine.translator.to_ai_message(response)
        message.chunk_id = chunk.chunk_id
        message.question = None
        if not message.correct_answer:
            message.correct_answer = chunk.correct_answer
        return _message_payload(message, source="teacher_skill_llm", extra={"askFollowUp": False})

    if support_mode == "progressive_explain" or user_request:
        user_msg = (
            f"用户现在不是在回答问题，而是在请求讲解：{user_request or '请直接解释这个知识点'}\n\n"
            "请进入渐进讲解模式，不要判卷，不要把用户当作答错。\n"
            "输出结构：\n"
            "1. 直接定义\n"
            "2. 材料里的作用\n"
            "3. 一个具体例子\n"
            "4. 容易混淆的边界\n"
            "5. 最后给一个轻量理解确认问题\n\n"
            f"=== 学习目标 ===\n{topic.title}\n\n"
            f"=== 知识点标题 ===\n{chunk.title}\n\n"
            f"=== 知识点内容 ===\n{chunk.content}\n\n"
            f"=== 原验证问题 ===\n{chunk.question}\n\n"
            f"=== 参考答案 ===\n{chunk.correct_answer}"
        )
        response = engine._call_llm(engine._get_system_prompt("teach"), user_msg)
        message = engine.translator.to_ai_message(response)
        message.chunk_id = chunk.chunk_id
        if not message.question:
            message.question = f"轻量确认：现在你能不能用一句话说出“{chunk.title}”是什么？"
        if not message.correct_answer:
            message.correct_answer = chunk.correct_answer
        return _message_payload(message, source="teacher_skill_llm")

    message = engine.start_topic(topic)
    return _message_payload(message, source="teacher_skill_llm")


def _real_judge_payload(payload: dict[str, Any]) -> dict[str, Any]:
    topic, _chunk = _topic_from_card_payload(payload)
    answer = _first_text(payload.get("answer"), payload.get("userAnswer"))
    engine = TutorEngine(user_id="web_user", topic_id=topic.topic_id)
    engine.topic_state = topic
    message = engine.receive_answer(answer, is_direct=False)
    response_type = getattr(message.response_type, "value", str(message.response_type))
    is_correct = response_type == ResponseType.FEEDBACK_CORRECT.value
    chunk = topic.chunks[0]
    return _message_payload(
        message,
        source="teacher_skill_llm",
        extra={
            "isCorrect": is_correct,
            "action": "next_chunk" if is_correct or message.is_final else "continue",
            "status": chunk.status.value,
            "card": {
                "hintLevel": chunk.hint_level,
                "failCount": chunk.fail_count,
                "attempts": chunk.attempts,
            },
        },
    )


def _real_hint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    topic, _chunk = _topic_from_card_payload(payload)
    direct = bool(payload.get("direct", False))
    answer = _first_text(payload.get("answer"), payload.get("userAnswer"), default="我还不会，请给我一个渐进提示。")
    engine = TutorEngine(user_id="web_user", topic_id=topic.topic_id)
    engine.topic_state = topic
    message = engine.receive_answer(answer, is_direct=direct)
    chunk = topic.chunks[0]
    return _message_payload(
        message,
        source="teacher_skill_llm",
        extra={
            "isCorrect": False,
            "action": "next_chunk" if direct or message.is_final else "continue",
            "status": chunk.status.value,
            "card": {
                "hintLevel": chunk.hint_level,
                "failCount": chunk.fail_count,
                "attempts": chunk.attempts,
            },
        },
    )


def _interactive_payload(
    payload: dict[str, Any],
    real_action: Callable[[dict[str, Any]], dict[str, Any]],
    fallback_action: Callable[[dict[str, Any], str], dict[str, Any]],
) -> dict[str, Any]:
    if not _card_from_payload(payload):
        raise ValueError("缺少知识卡片数据")
    use_real_engine = bool(payload.get("useRealEngine", True))
    if not use_real_engine:
        return fallback_action(payload, "已选择浏览器/本地规则模式")
    try:
        return _run_with_timeout(lambda: real_action(payload), timeout=18)
    except FutureTimeoutError:
        return fallback_action(payload, "真实引擎超过 18 秒未返回，已自动切换到稳定 fallback")
    except Exception as exc:
        return fallback_action(payload, f"真实引擎调用失败：{exc}")


def teach_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _interactive_payload(payload, _real_teach_payload, _fallback_teach)


def judge_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not _first_text(payload.get("answer"), payload.get("userAnswer")):
        raise ValueError("缺少用户回答")
    return _interactive_payload(payload, _real_judge_payload, _fallback_judge)


def hint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _interactive_payload(payload, _real_hint_payload, _fallback_hint)


def _classify_response_intent(user_input: str, chunk: ChunkState) -> str:
    value = user_input.strip()
    if not value:
        return "answer"

    direct_patterns = ["速查", "直接给答案", "给我答案", "告诉我答案", "正确答案", "标准答案", "看答案"]
    if any(pattern in value for pattern in direct_patterns):
        return "direct_answer"

    answer_cues = [
        "是一种",
        "是一个",
        "可以理解为",
        "类似",
        "相当于",
        "通过",
        "用于",
        "用来",
        "因为",
        "所以",
        "能够",
        "帮助",
        "组成",
        "基于",
        "属于",
        "解决",
        "适合",
        "边界",
        "例子",
    ]
    if len(value) >= 10 and any(cue in value for cue in answer_cues):
        return "answer"

    lowered = value.lower()
    title = (chunk.title or "").lower()
    if title and title in lowered and len(value) >= len(chunk.title) + 8:
        return "answer"

    explain_patterns = [
        "我不懂",
        "不太能",
        "不太会",
        "不太懂",
        "不理解",
        "不知道",
        "不会",
        "答不上来",
        "没懂",
        "看不懂",
        "直接讲",
        "直接说",
        "直接跟我说",
        "直接告诉我",
        "详细说",
        "详细讲",
        "解释一下",
        "讲解一下",
        "是什么",
        "什么意思",
        "教我",
        "帮我理解",
        "跟我说这个概念",
        "说这个概念",
        "告诉我这个概念",
        "可以直接",
        "展开说",
    ]
    if any(pattern in value for pattern in explain_patterns):
        return "explain"

    return "answer"


def _safe_json_dict(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _is_direct_explain_request(user_input: str) -> bool:
    direct_explain_patterns = [
        "不太能",
        "不太会",
        "答不上来",
        "直接讲",
        "直接说",
        "直接跟我说",
        "直接告诉我",
        "跟我说这个概念",
        "说这个概念",
        "告诉我这个概念",
        "可以直接",
    ]
    value = user_input.strip()
    return any(pattern in value for pattern in direct_explain_patterns)


def _classify_response_intent_with_llm(payload: dict[str, Any], chunk: ChunkState) -> str:
    user_input = _first_text(payload.get("userInput"), payload.get("answer"), payload.get("userRequest"))
    engine = TutorEngine(user_id="web_user", topic_id=f"web_intent_{uuid.uuid4().hex[:8]}")
    system_prompt = (
        "你是 Teacher-skill 的学习会话意图分类器。"
        "你只负责判断用户这句话应该进入哪一种学习动作，不要讲解知识点。\n\n"
        "只能返回 JSON，格式为：{\"intent\":\"answer|explain|direct_answer\"}。\n\n"
        "判别标准：\n"
        "1. answer：用户正在尝试回答当前验证问题，即使句子里包含“是什么”，只要后面给出了自己的理解、类比、原因、作用或例子，也算 answer。\n"
        "2. explain：用户明确表示不懂、不会、答不上来、想让老师直接讲、详细解释、从头讲、直接告诉他这个概念。\n"
        "3. direct_answer：用户要求直接看答案、标准答案、正确答案或速查答案。\n"
        "不要因为出现“是什么”三个字就自动判成 explain；也不要把“直接告诉我这个概念”判成 direct_answer。"
    )
    user_message = (
        f"当前知识卡片：{chunk.title}\n"
        f"验证问题：{chunk.question}\n"
        f"参考答案：{chunk.correct_answer}\n"
        f"用户输入：{user_input}\n\n"
        "请只返回 JSON。"
    )
    response = engine._call_llm(system_prompt, user_message, max_tokens=120)
    intent = str(_safe_json_dict(response).get("intent") or "").strip()
    if intent in {"answer", "explain", "direct_answer"}:
        return intent
    return _classify_response_intent(user_input, chunk)


def _route_response_payload(payload: dict[str, Any], intent: str, classifier_source: str) -> dict[str, Any]:
    user_input = _first_text(payload.get("userInput"), payload.get("answer"), payload.get("userRequest"))
    if intent == "direct_answer":
        result = hint_payload({**payload, "direct": True, "userRequest": user_input})
    elif intent == "explain":
        support_mode = "direct_explain" if _is_direct_explain_request(user_input) else "progressive_explain"
        result = teach_payload(
            {
                **payload,
                "userRequest": user_input,
                "supportMode": support_mode,
            }
        )
    else:
        result = judge_payload({**payload, "answer": user_input})

    result["intent"] = intent
    result["classifierSource"] = classifier_source
    return result


def respond_payload(payload: dict[str, Any]) -> dict[str, Any]:
    user_input = _first_text(payload.get("userInput"), payload.get("answer"), payload.get("userRequest"))
    if not user_input:
        raise ValueError("缺少用户输入")

    _topic, chunk = _topic_from_card_payload(payload)
    use_real_engine = bool(payload.get("useRealEngine", True))
    if not use_real_engine:
        intent = _classify_response_intent(user_input, chunk)
        return _route_response_payload(payload, intent, "local_router")

    try:
        intent = _run_with_timeout(
            lambda: _classify_response_intent_with_llm(payload, chunk),
            timeout=8,
        )
        return _route_response_payload(payload, intent, "teacher_skill_llm")
    except Exception:
        intent = _classify_response_intent(user_input, chunk)
        result = _route_response_payload(payload, intent, "local_router")
        result["intentFallbackReason"] = "LLM 意图判别不可用，已切换到本地路由规则"
        return result


def _run_real_engine(material: str, file_name: str, user_level: str) -> dict[str, Any]:
    cfg = get_config()
    cfg.llm.retry_count = min(cfg.llm.retry_count, 1)
    cfg.llm.timeout = min(cfg.llm.timeout, 12)
    cfg.llm.analysis_max_tokens = min(cfg.llm.analysis_max_tokens, 1600)
    topic_id = f"figma1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    engine = TutorEngine(user_id="figma1_user", topic_id=topic_id)
    topic = engine.analyze_material(material, user_level=user_level)
    return _topic_to_payload(topic, material, file_name)


def _extract_material(payload: dict[str, Any]) -> tuple[str, str, str]:
    file_name = _safe_filename(str(payload.get("fileName") or "material.txt"))
    file_data = payload.get("fileDataBase64")
    text = str(payload.get("text") or "")

    if file_data:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        upload_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file_name}"
        upload_path.write_bytes(base64.b64decode(str(file_data), validate=True))
        material = load_file(upload_path)
        return material, file_name, str(upload_path)

    return text.strip(), file_name, "manual"


def analyze_payload(payload: dict[str, Any]) -> dict[str, Any]:
    material, file_name, source_path = _extract_material(payload)
    if not material:
        raise ValueError("没有读取到可分析的材料内容")

    user_level = str(payload.get("userLevel") or "beginner")
    use_real_engine = bool(payload.get("useRealEngine", True))

    if not use_real_engine:
        result = _fallback_analysis(material, file_name, "已选择浏览器/本地规则模式")
    else:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_run_real_engine, material, file_name, user_level)
        try:
            result = future.result(timeout=25)
        except FutureTimeoutError:
            executor.shutdown(wait=False, cancel_futures=True)
            result = _fallback_analysis(material, file_name, "真实引擎超过 25 秒未返回，已自动切换到稳定 fallback")
        except Exception as exc:
            executor.shutdown(wait=False, cancel_futures=True)
            result = _fallback_analysis(material, file_name, f"真实引擎调用失败：{exc}")
        else:
            executor.shutdown(wait=False, cancel_futures=True)

    result["file"] = {
        "name": file_name,
        "sourcePath": source_path,
        "chars": len(material),
    }
    result["extractedText"] = material[:12000]
    return result


def web_demo_payload() -> dict[str, Any]:
    try:
        material = WEB_DEMO_MATERIAL_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        material = (
            "番茄工作法是一种简单的时间管理方法。它把工作切成 25 分钟专注和 5 分钟休息的循环，"
            "帮助学习者降低启动难度、减少分心，并在休息中恢复注意力。"
        )

    return {
        "ok": True,
        "mode": "recording_demo",
        "fileName": "录屏示例-番茄工作法.md",
        "goal": "帮我理解番茄工作法为什么能提升专注",
        "material": material,
        "suggestedQuestion": "不太能，可以直接跟我说这个概念。",
        "cards": [
            {
                "id": "recording_card_1",
                "title": "番茄工作法",
                "content": "番茄工作法把工作拆成短时间专注周期，让任务更容易开始和推进。",
                "difficulty": "easy",
                "question": "请用自己的话解释番茄工作法为什么能降低开始任务的难度。",
                "answer": "它把大任务切成 25 分钟左右的小周期，让人只需要先开始一个短时间段，而不是一次完成整个大任务。",
                "analogy": "像先跑一小段热身路，而不是一开始就要求自己跑完整场马拉松。",
                "status": "学习中",
            },
            {
                "id": "recording_card_2",
                "title": "25 分钟专注",
                "content": "25 分钟专注周期要求用户在一个短时间窗口里只处理一个明确任务。",
                "difficulty": "medium",
                "question": "为什么一次只做一件事能帮助减少分心？",
                "answer": "因为明确时间窗口和任务边界后，用户更容易拒绝消息、切换和临时打断。",
                "analogy": "像给注意力设一个临时围栏，先保护这一小段时间不被打断。",
                "status": "未开始",
            },
            {
                "id": "recording_card_3",
                "title": "休息恢复",
                "content": "短休息不是浪费时间，而是恢复注意力、降低疲劳的重要组成部分。",
                "difficulty": "easy",
                "question": "为什么休息也属于学习或工作的有效环节？",
                "answer": "因为持续专注会消耗注意力，短休息能帮助大脑恢复，让下一轮专注更稳定。",
                "analogy": "像手机短暂充电，目的是让下一段使用更稳定。",
                "status": "未开始",
            },
        ],
    }


class TeacherSkillApiHandler(BaseHTTPRequestHandler):
    server_version = "TeacherSkillLocalApi/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib API
        _json_response(self, 200, {"ok": True})

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        if self.path.startswith("/api/demo"):
            _json_response(self, 200, web_demo_payload())
            return

        if self.path.startswith("/api/health"):
            web_root = getattr(self.server, "web_root", _select_web_root())
            features = ["backend_intent_routing", "llm_intent_classifier", "progressive_explain", "direct_explain"]
            if bool(getattr(self.server, "recording_demo", False)):
                features.append("recording_demo")
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "service": "teacher-skill-local-api",
                    "supports": ["pdf", "txt", "md", "teach", "judge", "hint", "respond", "demo", "teacher_skill_llm", "fallback"],
                    "features": features,
                    "webRoot": str(web_root),
                },
            )
            return

        web_root = getattr(self.server, "web_root", _select_web_root())
        static_file = _resolve_static_file(web_root, self.path)
        if static_file is None:
            _json_response(self, 404, {"ok": False, "error": "Not found"})
            return
        _static_response(self, static_file)

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        path = urlparse(self.path).path
        handlers = {
            "/api/analyze": analyze_payload,
            "/api/teach": teach_payload,
            "/api/judge": judge_payload,
            "/api/hint": hint_payload,
            "/api/respond": respond_payload,
        }
        handler = handlers.get(path)
        if handler is None:
            _json_response(self, 404, {"ok": False, "error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
            result = handler(payload)
            _json_response(self, 200, result)
        except Exception as exc:  # Keep local demo server from crashing.
            _json_response(self, 400, {"ok": False, "error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[api] {self.address_string()} - {format % args}")


def run_server(
    host: str = HOST,
    port: int = PORT,
    web_root: Path | None = None,
    open_browser: bool = False,
    recording_demo: bool = False,
) -> None:
    selected_web_root = (web_root or _select_web_root()).resolve()
    server = ThreadingHTTPServer((host, port), TeacherSkillApiHandler)
    server.web_root = selected_web_root
    server.recording_demo = recording_demo
    url = f"http://{host}:{port}/"
    browser_url = f"{url}?demo=1" if recording_demo else url
    print(f"Teacher-skill local web running at {browser_url}")
    print(f"Serving local web assets from: {selected_web_root}")
    print("POST /api/analyze accepts PDF/txt/md base64 uploads or pasted text.")
    print("POST /api/teach, /api/judge, /api/hint and /api/respond power the web learning loop.")
    if recording_demo:
        print("Recording demo mode is enabled: GET /api/demo provides fixed offline demo data.")
    if open_browser:
        webbrowser.open(browser_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
