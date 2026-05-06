"""Scripted 3-minute product demo for Teacher-skill.

This demo is intentionally deterministic: it does not call the LLM API and it
does not wait for live user input. The goal is to make a boss-facing product
walkthrough finish reliably within three minutes while still showing the full
learning loop.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - only used before deps install
    def load_dotenv(*args, **kwargs) -> bool:
        return False

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from models.protocol import AIMessage, ResponseType
from models.state import ChunkState, LearningStatus, TopicState
from models.user import LearnedTopic, UserProfile
from src.core.memory import ConversationMemory
from src.utils.storage import TopicStorage


DEMO_USER_ID = "boss_demo_user"
DEMO_TOPIC_ID = "boss_demo_transformer"
DEMO_BUDGET_SECONDS = 180
DEFAULT_DELAY_SECONDS = 0.35

DEMO_MATERIAL = """Transformer 是一种基于注意力机制的深度学习架构。
它抛弃了 RNN 的逐步循环计算，用自注意力一次性建模序列中不同 token 之间的关系。
由于没有天然的顺序结构，Transformer 需要位置编码告诉模型每个 token 在序列中的位置。
多头注意力会并行学习多组关系，让模型同时捕捉语义、语法和长距离依赖。
"""


@dataclass(frozen=True)
class DemoSummary:
    """Compact result object returned by the scripted demo."""

    total: int
    mastered: int
    needs_review: int
    history_messages: int
    saved: bool
    elapsed_seconds: float


class BudgetGuard:
    """Keep the scripted demo within a hard runtime budget."""

    def __init__(self, max_seconds: int, delay_seconds: float) -> None:
        self.max_seconds = max_seconds
        self.delay_seconds = max(delay_seconds, 0)
        self.started_at = time.monotonic()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    def checkpoint(self, label: str) -> None:
        if self.elapsed > self.max_seconds:
            raise TimeoutError(
                f"Demo exceeded {self.max_seconds}s at step: {label}. "
                "Run with --fast for a no-delay version."
            )

    def pause(self) -> None:
        if self.delay_seconds <= 0:
            return
        remaining = self.max_seconds - self.elapsed
        if remaining <= 2:
            return
        time.sleep(min(self.delay_seconds, remaining - 2))


def configure_utf8() -> None:
    """Make Chinese CLI output readable on Windows terminals."""

    if sys.platform != "win32":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def build_demo_topic(
    user_id: str = DEMO_USER_ID,
    topic_id: str = DEMO_TOPIC_ID,
) -> TopicState:
    """Build a fixed topic state without using external services."""

    chunks = [
        ChunkState(
            chunk_id=f"{topic_id}_chunk_1",
            title="自注意力：从词到词的关系权重",
            content=(
                "自注意力会为当前 token 计算它和上下文中其他 token 的相关性，"
                "再按权重汇总信息。因此模型能直接找到一句话里真正相关的词。"
            ),
            question="如果一句话里的“它”指代前面的“模型”，自注意力主要在做什么？",
            options=[
                "A. 按顺序逐个读取 token",
                "B. 计算当前 token 和其他 token 的关系权重",
                "C. 只保留最后一个 token",
                "D. 把所有 token 随机打乱",
            ],
            correct_answer="B. 计算当前 token 和其他 token 的关系权重",
            analogy="像开会时根据当前议题，把注意力分给最相关的发言人。",
            difficulty="medium",
        ),
        ChunkState(
            chunk_id=f"{topic_id}_chunk_2",
            title="位置编码：给并行模型补上顺序感",
            content=(
                "Transformer 本身不按时间步循环读取序列，所以需要额外加入位置编码。"
                "位置编码让模型知道每个 token 在句子里的先后位置。"
            ),
            question="为什么 Transformer 需要位置编码？",
            options=[
                "A. 因为它没有 RNN 那样的天然顺序结构",
                "B. 因为它只能处理图片",
                "C. 因为它不能并行计算",
                "D. 因为它不需要上下文",
            ],
            correct_answer="A. 因为它没有 RNN 那样的天然顺序结构",
            analogy="像给一叠被打散的卡片标页码，模型才知道阅读顺序。",
            difficulty="easy",
        ),
        ChunkState(
            chunk_id=f"{topic_id}_chunk_3",
            title="多头注意力：并行观察多种关系",
            content=(
                "多头注意力会用多组注意力并行看同一段文本。"
                "不同头可以关注语法、指代、关键词或长距离依赖等不同关系。"
            ),
            question="多头注意力相比单头注意力的价值是什么？",
            options=[
                "A. 让模型只能关注一个关系",
                "B. 让多组注意力并行捕捉不同特征",
                "C. 取消所有权重计算",
                "D. 只提高输出字体大小",
            ],
            correct_answer="B. 让多组注意力并行捕捉不同特征",
            analogy="像一个评审小组从结构、含义、关键词多个角度同时看材料。",
            difficulty="medium",
        ),
    ]

    return TopicState(
        topic_id=topic_id,
        user_id=user_id,
        title="Transformer 入门学习闭环",
        summary="用 3 个知识卡片演示讲解、提问、判卷、速查和复习标记。",
        source_type="scripted_demo",
        source_path="demo_full_loop.py",
        material_chars=len(DEMO_MATERIAL),
        current_chunk_index=0,
        total_chunks=len(chunks),
        chunks=chunks,
    )


def make_ai_message(
    response_type: ResponseType,
    content: str,
    *,
    chunk: ChunkState | None = None,
    question: str | None = None,
    options: list[str] | None = None,
    hint_level: int = 0,
    is_final: bool = False,
) -> AIMessage:
    """Create an AIMessage for rendering and conversation history."""

    return AIMessage(
        response_type=response_type,
        content=content,
        chunk_id=chunk.chunk_id if chunk else None,
        question=question,
        options=options,
        hint_level=hint_level,
        is_final=is_final,
    )


def print_step(console: Console, number: int, title: str) -> None:
    console.print(f"\n[bold cyan]Step {number} / {title}[/bold cyan]")


def render_message(console: Console, message: AIMessage) -> None:
    """Render the scripted assistant output in a compact demo style."""

    if message.response_type == ResponseType.QUESTION:
        body = message.content
        if message.question:
            body += f"\n\n[bold]验证问题：[/bold]{message.question}"
        if message.options:
            body += "\n" + "\n".join(message.options)
        console.print(Panel(body, title="Teacher-skill", border_style="cyan"))
        return

    style_by_type = {
        ResponseType.EXPLANATION: "cyan",
        ResponseType.FEEDBACK_CORRECT: "green",
        ResponseType.FEEDBACK_WRONG: "yellow",
        ResponseType.DIRECT_ANSWER: "magenta",
    }
    title_by_type = {
        ResponseType.EXPLANATION: "讲解",
        ResponseType.FEEDBACK_CORRECT: "判卷反馈：通过",
        ResponseType.FEEDBACK_WRONG: "判卷反馈：需要提示",
        ResponseType.DIRECT_ANSWER: "速查模式",
    }
    console.print(
        Panel(
            message.content,
            title=title_by_type.get(message.response_type, "Teacher-skill"),
            border_style=style_by_type.get(message.response_type, "white"),
        )
    )


def render_material(console: Console) -> None:
    console.print(Panel(DEMO_MATERIAL.strip(), title="输入材料", border_style="white"))


def render_cards(console: Console, topic: TopicState) -> None:
    table = Table(title="AI 自动拆出的知识卡片")
    table.add_column("#", justify="right", width=3)
    table.add_column("知识点", style="bold")
    table.add_column("验证问题")
    table.add_column("难度", width=8)
    for index, chunk in enumerate(topic.chunks, start=1):
        table.add_row(str(index), chunk.title, chunk.question, chunk.difficulty)
    console.print(table)


def render_status_table(console: Console, topic: TopicState) -> None:
    labels = {
        LearningStatus.MASTERED: "已掌握",
        LearningStatus.NEEDS_REVIEW: "待巩固",
        LearningStatus.IN_PROGRESS: "学习中",
        LearningStatus.NOT_STARTED: "未开始",
    }
    table = Table(title="学习状态")
    table.add_column("知识点")
    table.add_column("状态")
    table.add_column("尝试")
    table.add_column("提示层级")
    for chunk in topic.chunks:
        table.add_row(
            chunk.title,
            labels[chunk.status],
            str(chunk.attempts),
            str(chunk.hint_level),
        )
    console.print(table)


def mark_correct(chunk: ChunkState) -> None:
    chunk.status = LearningStatus.MASTERED
    chunk.attempts += 1
    chunk.hint_level = 0


def mark_wrong_then_direct(chunk: ChunkState) -> None:
    chunk.status = LearningStatus.NEEDS_REVIEW
    chunk.attempts += 2
    chunk.fail_count += 1
    chunk.hint_level = 4


def save_and_restore(topic: TopicState, memory: ConversationMemory) -> TopicState:
    """Persist the demo state and read it back to prove resume capability."""

    mastered = sum(1 for chunk in topic.chunks if chunk.status == LearningStatus.MASTERED)
    needs_review = sum(
        1 for chunk in topic.chunks if chunk.status == LearningStatus.NEEDS_REVIEW
    )
    profile = UserProfile(
        user_id=topic.user_id,
        level="intermediate",
        familiar_topics=["神经网络", "注意力机制"],
        total_topics=1,
        completed_topics=1,
        history_topics=[
            LearnedTopic(
                topic_id=topic.topic_id,
                title=topic.title,
                summary=topic.summary,
                total_chunks=topic.total_chunks,
                mastered_chunks=mastered,
                review_chunks=needs_review,
                source_type=topic.source_type,
                source_path=topic.source_path,
            )
        ],
    )

    storage = TopicStorage(topic.user_id)
    storage.save_user_profile(profile.model_dump(mode="json"))
    storage.save_topic_state(topic.topic_id, topic.model_dump(mode="json"))
    storage.save_conversation_history(topic.topic_id, memory.messages)

    saved_state = storage.load_topic_state(topic.topic_id)
    if not saved_state:
        raise RuntimeError("Demo state was not saved correctly")
    return TopicState.model_validate(saved_state)


def run_demo(
    *,
    console: Console | None = None,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    max_seconds: int = DEMO_BUDGET_SECONDS,
    save: bool = True,
) -> DemoSummary:
    """Run the deterministic boss-facing demo."""

    console = console or Console()
    guard = BudgetGuard(max_seconds=max_seconds, delay_seconds=delay_seconds)
    topic = build_demo_topic()
    memory = ConversationMemory(topic.user_id, topic.topic_id)

    console.print(
        Panel(
            "[bold]Teacher-skill 固定 3 分钟 Demo[/bold]\n\n"
            "定位：把学习材料变成可验证的学习闭环。\n"
            "模式：固定脚本，不调用外部 LLM/API，不等待现场输入。\n"
            "展示点：拆卡片、讲解、提问、判卷、速查、保存恢复、学习报告。",
            border_style="cyan",
        )
    )
    guard.pause()

    print_step(console, 1, "输入材料")
    render_material(console)
    console.print("[dim]话术：我从一段普通学习材料开始，而不是手工配置题库。[/dim]")
    guard.checkpoint("material")
    guard.pause()

    print_step(console, 2, "自动拆成知识卡片")
    render_cards(console, topic)
    console.print("[dim]话术：系统把材料拆成可讲解、可提问、可判卷的最小学习单元。[/dim]")
    guard.checkpoint("cards")
    guard.pause()

    print_step(console, 3, "闭环一：讲解后提问，用户答对")
    chunk = topic.chunks[0]
    msg = make_ai_message(
        ResponseType.QUESTION,
        "先讲清概念，再立刻验证理解：自注意力不是顺序读词，而是在上下文里分配关注权重。",
        chunk=chunk,
        question=chunk.question,
        options=chunk.options,
    )
    render_message(console, msg)
    memory.add_ai_message(msg)
    user_answer = "选 B。它在计算当前 token 和上下文 token 的关系权重。"
    console.print(f"[bold blue]用户回答：[/bold blue]{user_answer}")
    memory.add_user_message(user_answer)
    mark_correct(chunk)
    feedback = make_ai_message(
        ResponseType.FEEDBACK_CORRECT,
        "答对。你抓住了核心：模型会根据当前 token，把注意力分配给最相关的上下文信息。",
        chunk=chunk,
    )
    render_message(console, feedback)
    memory.add_ai_message(feedback)
    topic.current_chunk_index = 1
    guard.checkpoint("correct loop")
    guard.pause()

    print_step(console, 4, "闭环二：用户答错，先提示，再速查")
    chunk = topic.chunks[1]
    msg = make_ai_message(
        ResponseType.QUESTION,
        "现在进入第二个知识点：位置编码解决的是顺序信息，而不是词向量本身。",
        chunk=chunk,
        question=chunk.question,
        options=chunk.options,
    )
    render_message(console, msg)
    memory.add_ai_message(msg)
    wrong_answer = "位置编码就是把词变成向量。"
    console.print(f"[bold blue]用户回答：[/bold blue]{wrong_answer}")
    memory.add_user_message(wrong_answer)
    hint = make_ai_message(
        ResponseType.FEEDBACK_WRONG,
        "还差一点。线索：Transformer 可以并行看完整句话，所以它需要额外知道 token 的先后位置。",
        chunk=chunk,
        hint_level=1,
    )
    render_message(console, hint)
    memory.add_ai_message(hint)
    console.print("[bold blue]用户指令：[/bold blue]/direct")
    memory.add_user_message("/direct")
    mark_wrong_then_direct(chunk)
    direct = make_ai_message(
        ResponseType.DIRECT_ANSWER,
        f"{chunk.content}\n\n系统动作：这个知识点已标记为“待巩固”，后续复习会优先出现。",
        chunk=chunk,
        is_final=True,
    )
    render_message(console, direct)
    memory.add_ai_message(direct)
    topic.current_chunk_index = 2
    guard.checkpoint("wrong/direct loop")
    guard.pause()

    print_step(console, 5, "闭环三：继续学习并完成本轮")
    chunk = topic.chunks[2]
    msg = make_ai_message(
        ResponseType.QUESTION,
        "多头注意力让模型从多个角度同时看同一段文本，而不是只学一种关系。",
        chunk=chunk,
        question=chunk.question,
        options=chunk.options,
    )
    render_message(console, msg)
    memory.add_ai_message(msg)
    user_answer = "选 B。多个注意力头并行捕捉不同特征。"
    console.print(f"[bold blue]用户回答：[/bold blue]{user_answer}")
    memory.add_user_message(user_answer)
    mark_correct(chunk)
    feedback = make_ai_message(
        ResponseType.FEEDBACK_CORRECT,
        "答对。这样一个主题里，系统已经知道哪些点掌握了，哪些点要回炉复习。",
        chunk=chunk,
    )
    render_message(console, feedback)
    memory.add_ai_message(feedback)
    topic.current_chunk_index = topic.total_chunks
    topic.is_completed = True
    guard.checkpoint("final loop")
    guard.pause()

    print_step(console, 6, "保存恢复与学习报告")
    restored_topic = save_and_restore(topic, memory) if save else topic
    render_status_table(console, restored_topic)
    mastered = sum(
        1 for chunk in restored_topic.chunks if chunk.status == LearningStatus.MASTERED
    )
    needs_review = sum(
        1 for chunk in restored_topic.chunks if chunk.status == LearningStatus.NEEDS_REVIEW
    )
    report = (
        f"本轮完成：{restored_topic.total_chunks}/{restored_topic.total_chunks}\n"
        f"已掌握：{mastered}\n"
        f"待巩固：{needs_review}\n"
        f"恢复验证：{'已写入 data/users 并成功读回' if save else '本次未写盘'}"
    )
    render_message(
        console,
        make_ai_message(ResponseType.EXPLANATION, report, is_final=True),
    )
    guard.checkpoint("report")

    elapsed = guard.elapsed
    console.print(
        Panel(
            f"[bold green]演示完成[/bold green]\n\n"
            f"实际脚本耗时：{elapsed:.1f}s / {max_seconds}s\n"
            "收束话术：这个项目展示的是我能把一个 AI 想法落成完整产品闭环，"
            "包括 CLI 入口、状态机、持久化、测试和可演示的稳定路径。",
            border_style="green",
        )
    )

    return DemoSummary(
        total=restored_topic.total_chunks,
        mastered=mastered,
        needs_review=needs_review,
        history_messages=len(memory.messages),
        saved=save,
        elapsed_seconds=elapsed,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic 3-minute Teacher-skill demo.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Disable pacing delays; useful for preflight checks.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Seconds to pause between demo beats. Default: 0.35.",
    )
    parser.add_argument(
        "--max-seconds",
        type=int,
        default=DEMO_BUDGET_SECONDS,
        help="Hard runtime budget. Default: 180.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write the demo state to data/users.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    configure_utf8()
    load_dotenv()
    args = parse_args(argv)
    delay = 0 if args.fast else args.delay
    run_demo(delay_seconds=delay, max_seconds=args.max_seconds, save=not args.no_save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
