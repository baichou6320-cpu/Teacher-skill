"""核心调度器 — 控制逻辑流转 (State Machine)

通过调用 LLM 实现「讲解→提问→反馈」的启发式学习闭环。
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from models.protocol import AIMessage, ResponseType, UserAnswer
from models.state import ChunkState, LearningStatus, TopicState
from src.core.memory import ConversationMemory
from src.core.rewards import RewardsCalculator
from src.llm.client import LLMClient
from src.llm.exceptions import LLMError
from src.llm.translator import ResponseTranslator
from src.utils.logger import get_logger


class TutorState(str, Enum):
    """Tutor state enumeration."""

    IDLE = "idle"
    ONBOARDING = "onboarding"
    ANALYZING = "analyzing"
    TEACHING = "teaching"
    WAITING_ANSWER = "waiting_answer"
    PROVIDING_HINT = "providing_hint"
    COMPLETED = "completed"


class TutorEngine:
    """Core scheduler that controls the learning flow via a state machine."""

    _WELCOME_MSG = (
        "欢迎使用 Teacher-skill！我是你的数字助教。\n\n"
        "在开始学习之前，让我先了解一下你的情况。\n\n"
        "你之前接触过机器学习/深度学习相关内容吗？"
        "是完全从零开始，还是有一些了解？"
    )

    def __init__(self, user_id: str, topic_id: str):
        self.user_id = user_id
        self.topic_id = topic_id
        self.state = TutorState.IDLE
        self.topic_state: Optional[TopicState] = None
        self._review_mode = False
        self._review_queue: list[int] = []
        self._review_position = 0

        self.memory = ConversationMemory(user_id, topic_id)
        self.rewards = RewardsCalculator()
        self.logger = get_logger("engine")

        api_key = LLMClient.interpolate("{{ANTHROPIC_API_KEY}}", {"ANTHROPIC_API_KEY": ""})
        # LLMClient will read the key from env internally
        self.llm = LLMClient()
        self.translator = ResponseTranslator()

        self._load_prompts()
        self.logger.debug("TutorEngine initialized")

    def _load_prompts(self) -> None:
        """Load prompt templates from the prompts/ directory."""
        import os
        from pathlib import Path

        from src.utils.config import get_config

        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        system_dir = prompts_dir / "system"
        cfg = get_config()
        self._prompt_mode = cfg.teaching.prompt_mode

        if self._prompt_mode == "split":
            self.logger.info("Prompt mode: split (layered architecture)")
            self._prompt_base = (prompts_dir / "_base.md").read_text(encoding="utf-8")
            self._prompt_persona = (prompts_dir / "_persona.md").read_text(
                encoding="utf-8"
            )
            self._prompt_onboarding = (system_dir / "00_onboarding.md").read_text(
                encoding="utf-8"
            )
            self._prompt_analyzer = (system_dir / "01_analyzer.md").read_text(
                encoding="utf-8"
            )
            self._prompt_teach = (system_dir / "02_teach.md").read_text(
                encoding="utf-8"
            )
            self._prompt_judge = (system_dir / "03_judge.md").read_text(
                encoding="utf-8"
            )
            self._prompt_review = (system_dir / "04_review.md").read_text(
                encoding="utf-8"
            )
        else:
            self.logger.info("Prompt mode: merged (backward compatible)")
            legacy_dir = prompts_dir / "legacy"
            self.prompt_onboarding = (legacy_dir / "00_onboarding.md").read_text(
                encoding="utf-8"
            )
            self.prompt_analyzer = (legacy_dir / "01_analyzer.md").read_text(
                encoding="utf-8"
            )
            self.prompt_tutor = (legacy_dir / "02_tutor_core.md").read_text(
                encoding="utf-8"
            )

    def _get_system_prompt(self, module: str) -> str:
        """Return the system prompt for a given module.

        In ``split`` mode, concatenates ``_base`` + ``_persona`` (if applicable)
        + the module-specific prompt.
        In ``merged`` mode, returns the legacy single-file prompts.

        Args:
            module: One of ``onboarding``, ``analyzer``, ``teach``, ``judge``, ``review``.

        Returns:
            The full system prompt text.
        """
        if self._prompt_mode == "split":
            parts = [self._prompt_base]
            if module in ("onboarding", "teach", "judge", "review"):
                parts.append(self._prompt_persona)
            module_map = {
                "onboarding": self._prompt_onboarding,
                "analyzer": self._prompt_analyzer,
                "teach": self._prompt_teach,
                "judge": self._prompt_judge,
                "review": self._prompt_review,
            }
            parts.append(module_map[module])
            return "\n\n---\n\n".join(parts)

        # merged mode — backward compatible
        if module == "onboarding":
            return self.prompt_onboarding
        if module == "analyzer":
            return self.prompt_analyzer
        return self.prompt_tutor

    def _call_llm(self, system_prompt: str, user_message: str, max_tokens: int | None = None) -> str:
        """Call the LLM and return raw response text."""
        self.logger.info(f"Calling LLM, prompt_len={len(system_prompt)}, user_len={len(user_message)}")
        kwargs = {"system_prompt": system_prompt, "user_message": user_message}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response = self.llm.generate(**kwargs)
        self.logger.info(f"LLM response received, len={len(response)}")
        return response

    # ─── Onboarding ───

    def start_onboarding(self) -> AIMessage:
        """Begin the onboarding flow."""
        self.logger.info("State: IDLE -> ONBOARDING")
        self.state = TutorState.ONBOARDING
        msg = AIMessage(response_type=ResponseType.EXPLANATION, content=self._WELCOME_MSG)
        self.memory.add_ai_message(msg)
        return msg

    def process_onboarding_answer(self, answer: str) -> dict:
        """Process onboarding answer and determine user level.

        Returns a dict with ``level``, ``familiar_topics``, and ``explanation``.
        """
        self.memory.add_user_message(answer)

        user_msg = f"用户的背景描述如下：\n\n{answer}\n\n请根据以上描述，判断用户的学习水平并输出 JSON。"
        from src.utils.config import get_config
        try:
            response = self._call_llm(
                self._get_system_prompt("onboarding"),
                user_msg,
                max_tokens=get_config().llm.onboarding_max_tokens,
            )
            parsed = self.translator.parse_json(response)

            if parsed and "level" in parsed:
                return {
                    "level": parsed.get("level", "beginner"),
                    "familiar_topics": parsed.get("familiar_topics", []),
                    "explanation": parsed.get("explanation", ""),
                }

            # Fallback: infer from keywords
            text = response.lower()
        except LLMError as exc:
            self.logger.warning(f"Onboarding LLM call failed: {exc}, using keyword fallback")
            text = answer.lower()

        if any(k in text for k in ["advanced", "高级", "很熟悉", "深入"]):
            return {"level": "advanced", "familiar_topics": [], "explanation": "根据描述推断为高级水平"}
        if any(k in text for k in ["intermediate", "中级", "有一些了解", "接触过"]):
            return {"level": "intermediate", "familiar_topics": [], "explanation": "根据描述推断为中级水平"}
        return {"level": "beginner", "familiar_topics": [], "explanation": "根据描述推断为初级水平"}

    # ─── Material Analysis ───

    def _request_material_analysis(self, material: str, user_level: str) -> dict:
        """Ask the LLM to analyze material and return parsed chunk data."""
        prompt = LLMClient.interpolate(
            self._get_system_prompt("analyzer"),
            {"material": material, "user_level": user_level},
        )
        from src.utils.config import get_config
        response = self._call_llm(
            prompt, "请分析以上材料，拆解为知识点", max_tokens=get_config().llm.analysis_max_tokens
        )

        parsed = self.translator.parse_material_analysis(response)
        if not parsed:
            self.logger.error("Material analysis parsing failed")
            raise ValueError("材料分析失败，无法解析 LLM 响应")
        return parsed

    def _build_chunks(
        self,
        parsed: dict,
        start_index: int = 0,
        preserve_chunk_ids: bool = True,
    ) -> list[ChunkState]:
        """Build ChunkState objects from parsed material analysis."""
        chunks = []
        self.logger.info(f"Material parsed into {len(parsed.get('chunks', []))} chunks")
        for i, chunk_data in enumerate(parsed.get("chunks", [])):
            chunk_id = chunk_data.get("chunk_id")
            if not preserve_chunk_ids or not chunk_id:
                chunk_id = f"{self.topic_id}_chunk_{start_index + i}"
            chunk = ChunkState(
                chunk_id=chunk_id,
                title=chunk_data.get("title", ""),
                content=chunk_data.get("content", ""),
                question=chunk_data.get("question", ""),
                options=chunk_data.get("options"),
                correct_answer=chunk_data.get("correct_answer", chunk_data.get("answer", "")),
                analogy=chunk_data.get("analogy"),
                difficulty=chunk_data.get("difficulty", "medium"),
            )
            chunks.append(chunk)
        return chunks

    def analyze_material(self, material: str, user_level: str = "beginner") -> TopicState:
        """Analyse learning material and break it into knowledge chunks."""
        self.logger.info(f"State: {self.state.value} -> ANALYZING, user_level={user_level}")
        self.state = TutorState.ANALYZING

        parsed = self._request_material_analysis(material, user_level)
        chunks = self._build_chunks(parsed)

        self.topic_state = TopicState(
            topic_id=self.topic_id,
            user_id=self.user_id,
            title=parsed.get("topic_title", parsed.get("title", "")),
            summary=parsed.get("summary", ""),
            material_chars=len(material),
            total_chunks=len(chunks),
            chunks=chunks,
        )
        return self.topic_state

    def append_material(self, material: str, user_level: str = "beginner") -> list[ChunkState]:
        """Analyze additional material and append its chunks to the active topic."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")

        previous_state = self.state
        previous_total = self.topic_state.total_chunks
        self.logger.info(
            f"Appending material to {self.topic_id}, previous_total={previous_total}, "
            f"user_level={user_level}"
        )
        self.state = TutorState.ANALYZING

        try:
            parsed = self._request_material_analysis(material, user_level)
            new_chunks = self._build_chunks(
                parsed,
                start_index=previous_total,
                preserve_chunk_ids=False,
            )
        except Exception:
            self.state = previous_state
            raise
        if not new_chunks:
            self.logger.warning("Append material produced no chunks")
            self.state = previous_state
            return []

        self.topic_state.chunks.extend(new_chunks)
        self.topic_state.total_chunks = len(self.topic_state.chunks)
        self.topic_state.updated_at = datetime.now()

        if self.topic_state.is_completed:
            self.topic_state.is_completed = False
            self.topic_state.current_chunk_index = previous_total

        self.memory.add_user_message(f"/load 追加材料（{len(material)} 字符）")
        self.logger.info(
            f"Appended {len(new_chunks)} chunks, total={self.topic_state.total_chunks}"
        )
        self.state = previous_state
        return new_chunks

    # ─── Teaching Loop ───

    def start_topic(self, topic_state: TopicState) -> AIMessage:
        """Start teaching a topic from its first (or current) chunk."""
        self.topic_state = topic_state
        self.logger.info(f"State: {self.state.value} -> TEACHING, chunks={topic_state.total_chunks}")
        self.state = TutorState.TEACHING
        return self._teach_current_chunk()

    def _teach_current_chunk(self) -> AIMessage:
        """Teach the current chunk and ask a validation question."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")

        idx = self.topic_state.current_chunk_index
        if idx >= self.topic_state.total_chunks:
            self.logger.info("State: TEACHING -> COMPLETED")
            self.state = TutorState.COMPLETED
            return AIMessage(
                response_type=ResponseType.EXPLANATION,
                content="🎉 恭喜！你已经完成了这个主题的学习！",
                is_final=True,
            )

        chunk = self.topic_state.chunks[idx]
        self.logger.info(f"Teaching chunk {idx+1}/{self.topic_state.total_chunks}: {chunk.title}")

        # Build teaching context
        parts = [
            f"当前知识点 ({idx + 1}/{self.topic_state.total_chunks}):",
            f"=== 知识点标题 ===\n{chunk.title}",
            f"=== 知识点内容 ===\n{chunk.content}",
            f"=== 验证问题 ===\n{chunk.question}",
        ]
        if chunk.options:
            parts.append("=== 选项 ===\n" + "\n".join(chunk.options))
        if chunk.analogy:
            parts.append(f"=== 生活类比（用于提示）===\n{chunk.analogy}")

        context = "\n\n".join(parts)
        user_msg = f"请为用户讲解以下知识点，然后提出验证问题。\n\n{context}\n\n请直接输出讲解内容和问题。"

        history = self.memory.get_context_for_llm(count=5)
        if history:
            user_msg = f"【之前的对话上下文】\n{history}\n\n{user_msg}"

        try:
            response = self._call_llm(self._get_system_prompt("teach"), user_msg)
            ai_msg = self.translator.to_ai_message(response)
        except LLMError as exc:
            self.logger.error(f"Teaching LLM call failed: {exc}")
            ai_msg = AIMessage(
                response_type=ResponseType.EXPLANATION,
                content=f"⚠️ 生成讲解内容时遇到问题: {exc}\n\n请稍后再试，或输入 /direct 跳过此题。",
                chunk_id=chunk.chunk_id,
            )

        ai_msg.chunk_id = chunk.chunk_id
        ai_msg.response_type = ResponseType.QUESTION

        self.memory.add_ai_message(ai_msg)
        self.logger.info("State: TEACHING -> WAITING_ANSWER")
        self.state = TutorState.WAITING_ANSWER
        return ai_msg

    def receive_answer(self, answer: str, is_direct: bool = False) -> AIMessage:
        """Receive a user answer, judge it, and generate feedback."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")

        idx = self.topic_state.current_chunk_index
        chunk = self.topic_state.chunks[idx]
        chunk.attempts += 1

        user_answer = UserAnswer(chunk_id=chunk.chunk_id, answer=answer, is_direct=is_direct)
        self.memory.add_user_message(answer, answer=user_answer)

        # Quick-reference mode
        if is_direct:
            chunk.status = LearningStatus.NEEDS_REVIEW
            self.state = TutorState.WAITING_ANSWER
            direct_msg = AIMessage(
                response_type=ResponseType.DIRECT_ANSWER,
                content=f"【速查模式】{chunk.content}\n\n该知识点已标记为'待巩固'，后续复习时需要重新学习。",
                chunk_id=chunk.chunk_id,
                is_final=True,
            )
            self.memory.add_ai_message(direct_msg)
            return direct_msg

        # Build judgment context
        parts = [
            f"当前知识点 ({idx + 1}/{self.topic_state.total_chunks}):",
            f"=== 知识点 ===\n{chunk.title}\n{chunk.content}",
            f"=== 问题 ===\n{chunk.question}",
        ]
        if chunk.options:
            parts.append("=== 选项 ===\n" + "\n".join(chunk.options))
        parts.extend([
            f"=== 用户回答 ===\n{answer}",
            f"=== 正确答案 ===\n{chunk.correct_answer}",
            f"=== 错误次数 ===\n{chunk.fail_count}",
            f"=== 当前提示层级 ===\n{chunk.hint_level}",
        ])
        if chunk.analogy:
            parts.append(f"=== 生活类比 ===\n{chunk.analogy}")

        context = "\n\n".join(parts)
        if self._review_mode:
            prompt_module = "review"
            user_msg = (
                f"请按复习模式判断用户是否仍然掌握该知识点。\n\n{context}\n\n"
                "复习判卷规则：\n"
                "- 如果用户抓住核心概念，is_correct=true，action=next_chunk\n"
                "- 如果用户未通过，给 120 字以内短反馈\n"
                "- 第一次未通过通常 action=continue，hint_level 递增到 1\n"
                "- 如果当前提示层级已 >= 1 或明显卡住，action=next_chunk，hint_level=2\n\n"
                '请以 JSON 格式输出：\n'
                '{\n  "is_correct": true/false,\n  "feedback": "简短复习反馈",\n  "hint_level": 0-2,\n  "action": "continue/next_chunk"\n}'
            )
        else:
            prompt_module = "judge"
            user_msg = (
                f"请判断用户回答是否正确，并给出反馈。\n\n{context}\n\n"
                "判断规则：\n"
                "- 如果正确（答对或方向正确），标记 is_correct: true\n"
                "- 如果错误，给出渐进式提示（hint_level 1-4）\n"
                "- hint_level=1: 提供线索提示\n"
                "- hint_level=2: 提供生活类比\n"
                "- hint_level=3: 提供半解析\n"
                "- hint_level=4+: 给出部分答案\n\n"
                '请以 JSON 格式输出：\n'
                '{\n  "is_correct": true/false,\n  "feedback": "反馈内容",\n  "hint_level": 1-4,\n  "action": "continue/next_chunk/complete"\n}'
            )

        history = self.memory.get_context_for_llm(count=5)
        if history:
            user_msg = f"【之前的对话上下文】\n{history}\n\n{user_msg}"

        from src.utils.config import get_config
        try:
            response = self._call_llm(
                self._get_system_prompt(prompt_module),
                user_msg,
                max_tokens=get_config().llm.judgment_max_tokens,
            )
            parsed = self.translator.parse_judgment(response)
        except LLMError as exc:
            self.logger.error(f"Judgment LLM call failed: {exc}")
            # Graceful fallback: treat as wrong answer with a generic hint
            parsed = {
                "is_correct": False,
                "feedback": f"⚠️ 判卷服务暂时不可用: {exc}\n\n你的答案是：{answer}\n\n正确答案是：{chunk.correct_answer}\n\n请对照答案自己判断一下，然后我们可以继续下一题。",
                "hint_level": min(chunk.hint_level + 1, 2 if self._review_mode else 4),
                "action": "continue",
            }

        is_correct = parsed.get("is_correct", False)
        feedback = parsed.get("feedback", "")
        action = parsed.get("action", "continue")

        if is_correct:
            chunk.status = LearningStatus.MASTERED
            chunk.mastered_at = datetime.now()
            self.state = TutorState.TEACHING
            self.logger.info(f"Chunk {chunk.chunk_id} MASTERED, streak={self.rewards._get_or_create(self.user_id, self.topic_id).consecutive_correct}")

            streak_info = self.rewards.calculate_streak(self.user_id, self.topic_id, True)
            if streak_info.get("encouragement"):
                feedback += f"\n\n{streak_info['encouragement']}"

            correct_msg = AIMessage(
                response_type=ResponseType.FEEDBACK_CORRECT,
                content=feedback,
                chunk_id=chunk.chunk_id,
            )
            self.memory.add_ai_message(correct_msg)
            return correct_msg

        # Incorrect answer
        chunk.fail_count += 1
        chunk.hint_level = min(parsed.get("hint_level", chunk.hint_level + 1), 4)
        self.logger.info(f"Chunk {chunk.chunk_id} wrong, fail_count={chunk.fail_count}, hint_level={chunk.hint_level}")
        self.state = TutorState.PROVIDING_HINT

        if action == "next_chunk":
            chunk.status = LearningStatus.NEEDS_REVIEW
            chunk.hint_level = 4
            if self._review_mode:
                self.state = TutorState.WAITING_ANSWER
                review_msg = AIMessage(
                    response_type=ResponseType.FEEDBACK_HINT,
                    content=(
                        f"{feedback}\n\n"
                        "这个知识点先保留为待巩固，我们继续下一道复习题。"
                    ),
                    chunk_id=chunk.chunk_id,
                    hint_level=chunk.hint_level,
                    is_final=True,
                )
                self.memory.add_ai_message(review_msg)
                return review_msg
            self.state = TutorState.TEACHING
            next_msg = self.next_chunk()
            self.memory.add_ai_message(next_msg)
            return next_msg

        wrong_msg = AIMessage(
            response_type=ResponseType.FEEDBACK_WRONG,
            content=feedback,
            chunk_id=chunk.chunk_id,
            hint_level=chunk.hint_level,
        )
        self.memory.add_ai_message(wrong_msg)
        return wrong_msg

    def next_chunk(self) -> AIMessage:
        """Advance to the next knowledge chunk."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")

        self.topic_state.current_chunk_index += 1
        self.topic_state.updated_at = datetime.now()
        self.logger.info(f"Advanced to chunk {self.topic_state.current_chunk_index + 1}/{self.topic_state.total_chunks}")

        if self.topic_state.current_chunk_index >= self.topic_state.total_chunks:
            self.topic_state.is_completed = True
            self.state = TutorState.COMPLETED
            self.logger.info("Topic completed")
            return AIMessage(
                response_type=ResponseType.EXPLANATION,
                content="🎉 恭喜完成学习！",
                is_final=True,
            )

        self.state = TutorState.TEACHING
        return self._teach_current_chunk()

    def skip_current_chunk(self) -> AIMessage:
        """Skip the current chunk and mark it as needing review."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")

        idx = self.topic_state.current_chunk_index
        if idx < self.topic_state.total_chunks:
            chunk = self.topic_state.chunks[idx]
            if chunk.status != LearningStatus.MASTERED:
                chunk.status = LearningStatus.NEEDS_REVIEW
            self.memory.add_user_message("/skip")
            self.logger.info(f"Skipped chunk {idx + 1}/{self.topic_state.total_chunks}")

        return self.next_chunk()

    def previous_chunk(self) -> AIMessage:
        """Move back to the previous chunk and teach it again."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")

        if self.topic_state.current_chunk_index <= 0:
            return AIMessage(
                response_type=ResponseType.EXPLANATION,
                content="已经是第一个知识点，不能再往前了。",
            )

        self.topic_state.current_chunk_index -= 1
        self.topic_state.is_completed = False
        self.topic_state.updated_at = datetime.now()
        self.memory.add_user_message("/back")
        self.logger.info(
            f"Moved back to chunk {self.topic_state.current_chunk_index + 1}/"
            f"{self.topic_state.total_chunks}"
        )
        self.state = TutorState.TEACHING
        return self._teach_current_chunk()

    def jump_to_chunk(self, chunk_number: int) -> AIMessage:
        """Jump to a 1-based chunk number and teach it again."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")
        if chunk_number < 1 or chunk_number > self.topic_state.total_chunks:
            raise ValueError(
                f"知识点编号必须在 1 到 {self.topic_state.total_chunks} 之间"
            )

        self.topic_state.current_chunk_index = chunk_number - 1
        self.topic_state.is_completed = False
        self.topic_state.updated_at = datetime.now()
        self.memory.add_user_message(f"/jump {chunk_number}")
        self.logger.info(f"Jumped to chunk {chunk_number}/{self.topic_state.total_chunks}")
        self.state = TutorState.TEACHING
        return self._teach_current_chunk()

    def start_review(self, topic_state: TopicState) -> AIMessage:
        """Start review mode by asking weak knowledge points first."""
        self.topic_state = topic_state
        self._review_mode = True
        self._review_queue = self._build_review_queue(topic_state)
        self._review_position = 0
        self.memory.add_user_message("/review-mode")
        self.logger.info(
            f"State: {self.state.value} -> WAITING_ANSWER, "
            f"review_items={len(self._review_queue)}"
        )

        if not self._review_queue:
            self.state = TutorState.COMPLETED
            self._review_mode = False
            return AIMessage(
                response_type=ResponseType.EXPLANATION,
                content="当前主题没有可复习的知识点。",
                is_final=True,
            )

        return self._ask_current_review_chunk()

    def next_review_chunk(self) -> AIMessage:
        """Advance to the next review item without re-teaching the chunk."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")
        if not self._review_mode:
            raise ValueError("Review mode not started")

        self._review_position += 1
        if self._review_position >= len(self._review_queue):
            self._review_mode = False
            self.state = TutorState.COMPLETED
            self.topic_state.updated_at = datetime.now()
            self.topic_state.is_completed = True
            return AIMessage(
                response_type=ResponseType.EXPLANATION,
                content="✅ 本轮复习完成。待巩固内容已经更新到当前主题进度里。",
                is_final=True,
            )

        return self._ask_current_review_chunk()

    def skip_review_chunk(self) -> AIMessage:
        """Skip the current review item and keep it marked as needing review."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")
        if not self._review_mode or not self._review_queue:
            raise ValueError("Review mode not started")

        idx = self._review_queue[self._review_position]
        chunk = self.topic_state.chunks[idx]
        chunk.status = LearningStatus.NEEDS_REVIEW
        self.memory.add_user_message("/skip")
        self.logger.info(f"Skipped review chunk {idx + 1}/{self.topic_state.total_chunks}")
        return self.next_review_chunk()

    def _ask_current_review_chunk(self) -> AIMessage:
        """Ask the current review question directly."""
        if not self.topic_state:
            raise ValueError("Topic state not initialized")
        idx = self._review_queue[self._review_position]
        self.topic_state.current_chunk_index = idx
        self.topic_state.updated_at = datetime.now()
        chunk = self.topic_state.chunks[idx]
        self.state = TutorState.WAITING_ANSWER
        self.logger.info(
            f"Reviewing chunk {idx + 1}/{self.topic_state.total_chunks}: {chunk.title}"
        )
        msg = AIMessage(
            response_type=ResponseType.QUESTION,
            content=(
                f"复习模式 ({self._review_position + 1}/{len(self._review_queue)})："
                "跳过讲解，直接验证这个知识点。"
            ),
            question=chunk.question,
            options=chunk.options,
            chunk_id=chunk.chunk_id,
        )
        self.memory.add_ai_message(msg)
        return msg

    def _build_review_queue(self, topic_state: TopicState) -> list[int]:
        """Prioritize review chunks: weak points, unfinished items, then mastered items."""
        weak: list[int] = []
        unfinished: list[int] = []
        mastered: list[int] = []

        for idx, chunk in enumerate(topic_state.chunks):
            if (
                chunk.status == LearningStatus.NEEDS_REVIEW
                or chunk.fail_count > 0
                or chunk.hint_level > 0
            ):
                weak.append(idx)
            elif chunk.status != LearningStatus.MASTERED:
                unfinished.append(idx)
            else:
                mastered.append(idx)

        return weak + unfinished + mastered

    def get_review_progress(self) -> str:
        """Return progress in the current review queue."""
        if not self._review_mode or not self._review_queue:
            return "未开始"
        return f"{self._review_position + 1}/{len(self._review_queue)}"

    def restore_memory(self, messages: list[dict]) -> None:
        """Restore conversation memory from persisted history."""
        self.memory.load_from_history(messages)
        self.logger.info(f"Memory restored: {len(messages)} messages")

    def get_state(self) -> TutorState:
        """Return the current tutor state."""
        return self.state

    def get_progress(self) -> str:
        """Return a human-readable progress string."""
        if not self.topic_state or self.topic_state.total_chunks == 0:
            return "未开始"
        return f"{self.topic_state.current_chunk_index + 1}/{self.topic_state.total_chunks}"
