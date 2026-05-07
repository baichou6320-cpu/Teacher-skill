"""Local HTTP bridge for the figma1 React prototype.

This server intentionally uses only the Python standard library plus the
project's existing runtime dependencies. It accepts PDF/txt/md uploads from the
frontend, extracts text through ``src.utils.file_loader``, and then tries to run
Teacher-skill's real ``TutorEngine.analyze_material`` flow.
"""
from __future__ import annotations

import base64
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

from models.state import TopicState
from src.core.engine import TutorEngine
from src.llm.exceptions import LLMError
from src.utils.config import get_config
from src.utils.file_loader import load_file


PROJECT_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = PROJECT_ROOT / ".tmp" / "figma1_uploads"
HOST = "127.0.0.1"
PORT = 8765

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


class TeacherSkillApiHandler(BaseHTTPRequestHandler):
    server_version = "TeacherSkillLocalApi/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib API
        _json_response(self, 200, {"ok": True})

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        if self.path.startswith("/api/health"):
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "service": "teacher-skill-local-api",
                    "supports": ["pdf", "txt", "md", "teacher_skill_llm", "fallback"],
                },
            )
            return
        _json_response(self, 404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        if not self.path.startswith("/api/analyze"):
            _json_response(self, 404, {"ok": False, "error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
            result = analyze_payload(payload)
            _json_response(self, 200, result)
        except Exception as exc:  # Keep local demo server from crashing.
            _json_response(self, 400, {"ok": False, "error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[api] {self.address_string()} - {format % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), TeacherSkillApiHandler)
    print(f"Teacher-skill local API running at http://{HOST}:{PORT}")
    print("POST /api/analyze accepts PDF/txt/md base64 uploads or pasted text.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
