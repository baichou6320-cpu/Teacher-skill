"""结构化解析器 — 将 LLM 的 JSON/文本响应转化为 Python 对象。"""
import json
import re
from typing import Optional

from models.protocol import AIMessage, ResponseType
from src.utils.logger import get_logger


class ResponseTranslator:
    """Robust parser for LLM responses.

    Handles various output formats including:
    - Standard JSON
    - JSON wrapped in ```json ... ``` blocks
    - Mixed content (thinking + JSON)
    - Plain text fallback with keyword heuristics
    """

    def __init__(self):
        self.logger = get_logger("translator")

    def parse_json(self, text: str) -> Optional[dict]:
        """Extract a JSON object from text, with 4-level fallback."""
        if not text or not text.strip():
            return None

        text = text.strip()

        # 1. Extract from ```json ... ``` block
        m = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                self.logger.debug("JSON block extraction failed, trying next strategy")
                pass

        # 2. Extract from ``` ... ``` block (any language)
        m = re.search(r"```\s*([\s\S]*?)\s*```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Extract outermost {...} by matching braces
        brace_match = self._extract_balanced_json(text)
        if brace_match:
            try:
                return json.loads(brace_match)
            except json.JSONDecodeError:
                self.logger.debug("Balanced brace extraction failed, trying direct parse")
                pass

        # 4. Direct parse
        try:
            result = json.loads(text)
            return result if isinstance(result, dict) else None
        except json.JSONDecodeError:
            self.logger.warning(f"All JSON extraction strategies failed for text (len={len(text)})")
            return None

    @staticmethod
    def _extract_balanced_json(text: str) -> Optional[str]:
        """Find the first balanced {...} object in text."""
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    def parse_material_analysis(self, response: str) -> Optional[dict]:
        """Parse the material-analysis response (01_analyzer.md).

        Returns a dict with ``topic_title``, ``topic_id``, and ``chunks`` list.
        Falls back to regex extraction if JSON parsing fails.
        """
        parsed = self.parse_json(response)
        if parsed is not None:
            self.logger.info(f"Material analysis parsed: {len(parsed.get('chunks', []))} chunks")
            # Normalise field names: 'answer' -> 'correct_answer'
            for chunk in parsed.get("chunks", []):
                if "answer" in chunk and "correct_answer" not in chunk:
                    chunk["correct_answer"] = chunk.pop("answer")
            return parsed

        # Fallback: manual regex extraction for broken JSON
        self.logger.warning("Material analysis JSON parse failed, falling back to regex extraction")
        return self._fallback_extract_material(response)

    def _fallback_extract_material(self, text: str) -> Optional[dict]:
        """Emergency extraction when JSON is completely broken."""
        result: dict = {}

        # topic_title
        m = re.search(r'"topic_title"\s*:\s*"([^"]+)"', text)
        if m:
            result["topic_title"] = m.group(1)

        # topic_id
        m = re.search(r'"topic_id"\s*:\s*"([^"]+)"', text)
        if m:
            result["topic_id"] = m.group(1)

        # Try to find chunks array content
        chunks_match = re.search(r'"chunks"\s*:\s*\[(.*?)\]\s*,?\s*(?:"topic|\})', text, re.DOTALL)
        if not chunks_match:
            chunks_match = re.search(r'"chunks"\s*:\s*\[(.*)\]', text, re.DOTALL)

        chunks: list[dict] = []
        if chunks_match:
            chunks_text = chunks_match.group(1)
            # Extract individual chunk objects
            for chunk_json in self._iter_json_objects(chunks_text):
                chunk = self._parse_chunk_fields(chunk_json)
                if chunk.get("chunk_id") or chunk.get("title"):
                    chunks.append(chunk)

        if chunks:
            result["chunks"] = chunks

        return result if result.get("chunks") else None

    @staticmethod
    def _iter_json_objects(text: str):
        """Yield balanced {...} substrings from text."""
        depth = 0
        start = None
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    yield text[start : i + 1]
                    start = None

    @staticmethod
    def _parse_chunk_fields(chunk_text: str) -> dict:
        """Extract known fields from a chunk JSON snippet."""
        chunk: dict = {}
        string_fields = [
            "chunk_id",
            "title",
            "content",
            "question",
            "answer",
            "analogy",
            "difficulty",
            "correct_answer",
        ]
        for field in string_fields:
            m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', chunk_text)
            if m:
                chunk[field] = m.group(1)

        # options array
        m = re.search(r'"options"\s*:\s*\[([^\]]+)\]', chunk_text)
        if m:
            opts = [opt.strip().strip('"').strip("'") for opt in m.group(1).split(",")]
            chunk["options"] = [o for o in opts if o]

        # Normalise answer -> correct_answer
        if "answer" in chunk and "correct_answer" not in chunk:
            chunk["correct_answer"] = chunk.pop("answer")

        return chunk

    def parse_judgment(self, response: str) -> dict:
        """Parse a judgment response.

        Expected format::

            {"is_correct": true, "feedback": "...", "hint_level": 1, "action": "continue"}

        Returns a dict with at least ``is_correct``, ``feedback``, ``hint_level``, ``action``.
        """
        parsed = self.parse_json(response)
        if parsed is not None:
            self.logger.debug(f"Judgment parsed: is_correct={parsed.get('is_correct')}")
            # Handle AIMessage-style format (has response_type)
            if "response_type" in parsed:
                rt = parsed.get("response_type", "")
                is_correct = rt == "feedback_correct"
                return {
                    "is_correct": is_correct,
                    "feedback": parsed.get("content", ""),
                    "hint_level": parsed.get("hint_level", 0),
                    "action": "next_chunk" if is_correct else "continue",
                }
            # Standard judgment format
            return {
                "is_correct": parsed.get("is_correct", False),
                "feedback": parsed.get("feedback", ""),
                "hint_level": parsed.get("hint_level", 0),
                "action": parsed.get("action", "continue"),
            }

        # Ultimate fallback: keyword heuristics on raw text
        self.logger.warning("Judgment JSON parse failed, using keyword fallback")
        return self._fallback_judgment(response)

    @staticmethod
    def _fallback_judgment(text: str) -> dict:
        """Infer judgment from plain text using keyword heuristics."""
        lower = text.lower()
        result = {
            "is_correct": False,
            "feedback": text.strip(),
            "hint_level": 1,
            "action": "continue",
        }

        # Correct indicators (strong signals)
        correct_signals = ["✅", "完全正确", "答对了", "非常好", "正确！", "正确。"]
        wrong_signals = ["❌", "答错了", "不太对", "不正确"]
        next_signals = ["下一知识点", "进入下一个", "继续学习下一个"]

        if any(s in lower for s in correct_signals):
            result["is_correct"] = True
            result["action"] = "next_chunk"
        elif any(s in lower for s in wrong_signals):
            result["is_correct"] = False
            result["action"] = "continue"
        elif any(s in lower for s in next_signals):
            result["action"] = "next_chunk"

        return result

    def to_ai_message(self, raw_response: str) -> AIMessage:
        """Convert an LLM raw response into an AIMessage."""
        parsed = self.parse_json(raw_response)
        if parsed:
            self.logger.debug("AIMessage parsed from JSON")
            return self._from_json(parsed)
        self.logger.debug("AIMessage inferred from text")
        return self._from_text(raw_response)

    @staticmethod
    def _from_json(data: dict) -> AIMessage:
        """Create AIMessage from a parsed JSON dict."""
        rt_str = data.get("response_type", "explanation")
        try:
            response_type = ResponseType(rt_str)
        except ValueError:
            response_type = ResponseType.EXPLANATION

        return AIMessage(
            response_type=response_type,
            content=data.get("content", data.get("feedback", "")),
            chunk_id=data.get("chunk_id"),
            question=data.get("question"),
            options=data.get("options"),
            correct_answer=data.get("correct_answer"),
            hint_level=data.get("hint_level", 0),
            is_final=data.get("is_final", False),
        )

    @staticmethod
    def _from_text(text: str) -> AIMessage:
        """Infer an AIMessage from plain text."""
        stripped = text.strip()
        if not stripped:
            return AIMessage(
                response_type=ResponseType.EXPLANATION,
                content="（模型未返回有效内容）",
            )

        lower = stripped.lower()

        # Determine response type by heuristic
        if "?" in stripped and ("：" in stripped or ":" in stripped):
            rt = ResponseType.QUESTION
        elif any(s in lower for s in ["✅", "答对了", "非常好", "完全正确"]):
            rt = ResponseType.FEEDBACK_CORRECT
        elif any(s in lower for s in ["❌", "答错了", "不太对", "不正确"]):
            rt = ResponseType.FEEDBACK_WRONG
        elif any(s in lower for s in ["💡", "想想看", "再想想", "提示"]):
            rt = ResponseType.FEEDBACK_HINT
        elif any(s in lower for s in ["/direct", "速查", "直接给答案"]):
            rt = ResponseType.DIRECT_ANSWER
        else:
            rt = ResponseType.EXPLANATION

        return AIMessage(response_type=rt, content=stripped)
