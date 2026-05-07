"""Dependency-light local server for recording the Teacher-skill web demo.

This module is intentionally standard-library only. It lets
``python main.py --web --recording-demo`` run even before the full LLM/runtime
dependencies are installed, which makes short product recordings repeatable.
"""
from __future__ import annotations

import json
import mimetypes
import re
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
SHOWCASE_DIR = PROJECT_ROOT / "showcase"
WEB_DEMO_MATERIAL_PATH = PROJECT_ROOT / "samples" / "demo_article.md"
HOST = "127.0.0.1"
PORT = 8765


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def web_demo_payload() -> dict[str, Any]:
    try:
        material = WEB_DEMO_MATERIAL_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        material = (
            "番茄工作法是一种简单的时间管理方法。它把工作切成 25 分钟专注和 "
            "5 分钟休息的循环，帮助学习者降低启动难度、减少分心，并在休息中恢复注意力。"
        )

    cards = [
        {
            "id": "demo_pomodoro",
            "title": "番茄工作法",
            "content": "番茄工作法把任务拆成短时间专注和短休息的循环，降低开始学习的心理阻力。",
            "question": "请用自己的话解释“番茄工作法”为什么能帮助提升专注。",
            "answer": "它通过固定时段降低启动难度，用短休息恢复注意力，让学习者更容易持续推进任务。",
            "analogy": "像把一场长跑拆成几段可完成的小跑，每跑完一段就短暂恢复。",
            "difficulty": "easy",
        },
        {
            "id": "demo_focus_block",
            "title": "25 分钟专注",
            "content": "25 分钟专注给学习者一个明确边界，减少一开始就面对长任务的压力。",
            "question": "为什么 25 分钟这种短专注块，比直接要求自己学 3 小时更容易开始？",
            "answer": "因为短时间目标更具体，心理压力更低，也更容易屏蔽临时分心。",
            "analogy": "像先完成一个小台阶，而不是一开始就盯着整座楼梯。",
            "difficulty": "easy",
        },
        {
            "id": "demo_recovery",
            "title": "休息恢复",
            "content": "短休息不是偷懒，而是帮助注意力恢复，避免长时间硬撑造成效率下降。",
            "question": "为什么番茄工作法强调休息，而不是只强调更久地坚持？",
            "answer": "休息能恢复注意力和情绪能量，让下一轮专注更稳定。",
            "analogy": "像给电池短暂补电，避免一直低电量运行。",
            "difficulty": "easy",
        },
    ]

    return {
        "ok": True,
        "mode": "recording_demo",
        "fileName": "录屏示例-番茄工作法.md",
        "goal": "帮我理解番茄工作法为什么能提升专注",
        "material": material,
        "suggestedQuestion": "不太能，可以直接跟我说这个概念。",
        "cards": cards,
        "chunks": cards,
        "concepts": cards,
        "questions": [card["question"] for card in cards],
    }


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_static_file(request_path: str) -> Path | None:
    root = SHOWCASE_DIR.resolve()
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


def _card_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    card = payload.get("card")
    if isinstance(card, dict):
        return card
    cards = web_demo_payload()["cards"]
    return cards[0]


def _base_card_state(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "hintLevel": int(card.get("hintLevel") or card.get("hint_level") or 0),
        "failCount": int(card.get("failCount") or card.get("fail_count") or 0),
        "attempts": int(card.get("attempts") or 0),
    }


def _teach_payload(payload: dict[str, Any]) -> dict[str, Any]:
    card = _card_from_payload(payload)
    title = _first_text(card.get("title"), default="当前知识点")
    answer = _first_text(card.get("answer"), card.get("correctAnswer"), card.get("content"))
    content = _first_text(card.get("content"), answer)
    analogy = _first_text(card.get("analogy"), default=f"可以把“{title}”看成帮助你组织理解顺序的抓手。")
    support_mode = _first_text(payload.get("supportMode"))

    if support_mode == "direct_explain":
        return {
            "ok": True,
            "source": "recording_demo",
            "responseType": "explanation",
            "content": (
                f"我先直接讲“{title}”。\n\n"
                f"1. 它是什么：{content}\n\n"
                f"2. 它解决什么问题：它帮助你把一个大目标拆成更容易开始、也更容易坚持的小过程。\n\n"
                f"3. 类比理解：{analogy}\n\n"
                "4. 边界：它不是让人机械计时，而是用固定节奏降低分心和拖延。\n\n"
                f"一句话总结：{answer}"
            ),
            "question": None,
            "askFollowUp": False,
            "correctAnswer": answer,
            "card": _base_card_state(card),
        }

    progressive = support_mode == "progressive_explain" or bool(payload.get("userRequest"))
    return {
        "ok": True,
        "source": "recording_demo",
        "responseType": "question",
        "content": (
            f"我们一步步看“{title}”。先不用背答案，只抓三个点：\n\n"
            f"1. 定义：{content}\n\n"
            "2. 作用：它把模糊的大任务拆成一个可以马上开始的小循环。\n\n"
            f"3. 类比：{analogy}\n\n"
            "你先只要能说清楚它为什么降低开始难度，就已经抓住主线了。"
        ),
        "question": f"轻量确认：现在你能不能用一句话说出“{title}”是什么？" if progressive else card.get("question"),
        "askFollowUp": True,
        "correctAnswer": answer,
        "card": _base_card_state(card),
    }


def _hint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    card = _card_from_payload(payload)
    title = _first_text(card.get("title"), default="当前知识点")
    answer = _first_text(card.get("answer"), card.get("correctAnswer"), card.get("content"))
    direct = bool(payload.get("direct"))
    if direct:
        return {
            "ok": True,
            "source": "recording_demo",
            "responseType": "direct_answer",
            "intent": "direct_answer",
            "content": f"参考答案：{answer} 这张卡片会进入待巩固，之后建议再闭卷回答一次。",
            "isCorrect": False,
            "action": "next_chunk",
            "status": "needs_review",
            "card": {"hintLevel": 4, "failCount": 1, "attempts": 1},
        }

    return {
        "ok": True,
        "source": "recording_demo",
        "responseType": "feedback_hint",
        "content": f"提示：先别急着背定义，先说“{title}”解决了什么问题，再补一个例子。",
        "isCorrect": False,
        "action": "continue",
        "status": "in_progress",
        "card": {"hintLevel": 1, "failCount": 1, "attempts": 1},
    }


def _judge_payload(payload: dict[str, Any]) -> dict[str, Any]:
    card = _card_from_payload(payload)
    title = _first_text(card.get("title"), default="当前知识点")
    answer = _first_text(payload.get("answer"), payload.get("userAnswer"), payload.get("userInput"))
    lowered = answer.lower()
    is_unknown = bool(re.search(r"不会|不懂|不清楚|不知道|答不上", answer))
    is_correct = len(answer) >= 8 and not is_unknown and any(
        keyword in lowered
        for keyword in ["番茄", "25", "专注", "休息", "降低", "恢复", "循环", title.lower()]
    )

    if is_correct:
        return {
            "ok": True,
            "source": "recording_demo",
            "responseType": "feedback_correct",
            "intent": "answer",
            "content": f"方向对了。你已经抓住“{title}”的核心：它不是只看时间，而是用节奏帮助人持续专注。",
            "isCorrect": True,
            "action": "next_chunk",
            "status": "mastered",
            "card": {"hintLevel": 0, "failCount": 0, "attempts": 1},
        }

    result = _hint_payload(payload)
    result["intent"] = "answer"
    return result


def _respond_payload(payload: dict[str, Any]) -> dict[str, Any]:
    user_input = _first_text(payload.get("userInput"), payload.get("answer"), payload.get("userAnswer"))
    if re.search(r"直接.*(讲|说|解释)|不懂|不会|不太能|答不上|是什么", user_input):
        payload = {**payload, "supportMode": "direct_explain", "userRequest": user_input}
        result = _teach_payload(payload)
        result["intent"] = "explain"
        return result
    if re.search(r"答案|速查|直接给", user_input):
        result = _hint_payload({**payload, "direct": True})
        result["intent"] = "direct_answer"
        return result
    return _judge_payload(payload)


class RecordingDemoHandler(BaseHTTPRequestHandler):
    """Serve the recording demo website and deterministic local API responses."""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib API
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        path = urlparse(self.path).path
        if path == "/api/demo":
            _json_response(self, 200, web_demo_payload())
            return
        if path == "/api/health":
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "mode": "recording_demo",
                    "supports": ["demo", "teach", "judge", "hint", "respond", "recording_demo"],
                    "features": ["fixed_demo_data", "offline_responses", "no_runtime_dependencies"],
                },
            )
            return

        static_file = _resolve_static_file(self.path)
        if static_file is None:
            _json_response(self, 404, {"ok": False, "error": "Not found"})
            return
        _static_response(self, static_file)

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        path = urlparse(self.path).path
        payload = _read_json(self)
        if path == "/api/analyze":
            _json_response(self, 200, web_demo_payload())
            return
        if path == "/api/teach":
            _json_response(self, 200, _teach_payload(payload))
            return
        if path == "/api/judge":
            _json_response(self, 200, _judge_payload(payload))
            return
        if path == "/api/hint":
            _json_response(self, 200, _hint_payload(payload))
            return
        if path == "/api/respond":
            _json_response(self, 200, _respond_payload(payload))
            return
        _json_response(self, 404, {"ok": False, "error": "Not found"})


def run_server(
    host: str = HOST,
    port: int = PORT,
    open_browser: bool = False,
    recording_demo: bool = True,
) -> None:
    server = ThreadingHTTPServer((host, port), RecordingDemoHandler)
    url = f"http://{host}:{port}/?demo=1"
    print(f"Teacher-skill recording demo running at {url}")
    print("This mode uses fixed offline data and does not require API keys or LLM dependencies.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTeacher-skill recording demo stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server(open_browser=True)

