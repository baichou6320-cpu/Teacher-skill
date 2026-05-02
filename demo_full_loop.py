"""
Phase 1 教学闭环完整演示

自动模拟用户学习 Transformer 的完整流程：
材料输入 → 分析切片 → 讲解 → 提问 → 答对/答错/速查 → 学习报告
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tests  # noqa: F401  bootstrap env + UTF-8 fix

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.engine import TutorEngine
from src.core.memory import ConversationMemory
from src.utils.storage import TopicStorage
from models.protocol import ResponseType
from models.state import LearningStatus
from models.user import UserProfile

console = Console()


def print_banner():
    console.print(Panel.fit(
        "[bold cyan]🎓 Teacher-skill — Phase 1 教学闭环演示[/bold cyan]\n\n"
        "学习主题：Transformer\n"
        "流程：材料输入 → AI分析 → 讲解 → 提问 → 反馈 → 循环",
        border_style="cyan"
    ))
    console.print()


def print_step(num: int, title: str):
    console.print(f"\n[bold yellow]━━━ Step {num}: {title} ━━━[/bold yellow]")


def display_ai_message(msg):
    """Render AI message like main.py does."""
    console.print()
    if msg.response_type == ResponseType.EXPLANATION:
        console.print(f"[cyan]{msg.content}[/cyan]")
    elif msg.response_type == ResponseType.QUESTION:
        console.print(f"[bold yellow]📝 {msg.question}[/bold yellow]")
        if msg.options:
            for opt in msg.options:
                console.print(f"  {opt}")
    elif msg.response_type == ResponseType.FEEDBACK_CORRECT:
        console.print(f"[green]✅ {msg.content}[/green]")
    elif msg.response_type == ResponseType.FEEDBACK_WRONG:
        console.print(f"[red]❌ {msg.content}[/red]")
        if msg.hint_level > 0:
            console.print(f"[dim]提示等级: {msg.hint_level}[/dim]")
    elif msg.response_type == ResponseType.DIRECT_ANSWER:
        console.print(Panel.fit(
            f"[bold yellow]【速查模式】[/bold yellow]\n\n{msg.content}",
            border_style="yellow"
        ))


def main():
    print_banner()

    # ─── Setup ───
    user_id = "demo_user"
    topic_id = "demo_transformer"
    engine = TutorEngine(user_id, topic_id)
    storage = TopicStorage(user_id)

    # ─── Step 1: Onboarding ───
    print_step(1, "用户水平摸底")
    onboarding_msg = engine.start_onboarding()
    display_ai_message(onboarding_msg)

    user_background = "我有一些基础了解，之前学过神经网络和注意力机制"
    console.print(f"\n[dim]> {user_background}[/dim]")
    result = engine.process_onboarding_answer(user_background)
    level = result["level"]
    console.print(f"\n[green]✅ 判定学习水平：{level}[/green]")

    profile = UserProfile(user_id=user_id, level=level)
    storage.save_user_profile(profile.model_dump())

    # ─── Step 2: Material Input ───
    print_step(2, "输入学习材料")
    material = """
Transformer是一种革命性的深度学习架构，它在2017年的论文《Attention Is All You Need》中被提出。

核心创新：
1. 自注意力机制（Self-Attention）：让模型能够同时关注输入序列的不同位置，计算 token 之间的相关性权重。
2. 位置编码（Positional Encoding）：因为没有循环结构，需要手动添加位置信息，让模型知道每个词在序列中的位置。
3. 多头注意力（Multi-Head Attention）：多组注意力机制并行学习不同特征，类似于 CNN 中的多通道。

Transformer的优势：
- 可以并行计算，训练速度比 RNN/LSTM 快很多
- 能够捕捉长距离依赖关系
- 容易扩展到更大的模型规模
"""
    console.print(f"[dim]材料长度：{len(material)} 字符[/dim]")
    console.print("[dim]正在调用 LLM 分析材料...[/dim]")

    topic_state = engine.analyze_material(material, user_level=level)

    # ─── Step 3: Show Analysis Result ───
    print_step(3, "材料分析结果")
    console.print(Panel.fit(
        f"[bold green]✅ 分析完成！[/bold green]\n"
        f"知识点数量：{topic_state.total_chunks} 个",
        border_style="green"
    ))

    table = Table(title="📚 知识卡片")
    table.add_column("序号", style="cyan", width=4)
    table.add_column("标题", style="white")
    table.add_column("问题", style="dim")
    for i, chunk in enumerate(topic_state.chunks):
        table.add_row(str(i + 1), chunk.title, chunk.question[:40] + "...")
    console.print(table)

    # ─── Step 4: Learning Loop ───
    print_step(4, "教学循环开始")

    # Start first chunk
    response = engine.start_topic(topic_state)
    current_idx = 0

    while current_idx < topic_state.total_chunks and current_idx < 3:  # Demo: max 3 chunks
        chunk = topic_state.chunks[current_idx]
        display_ai_message(response)

        # Simulate user answering
        if current_idx == 0:
            # Chunk 1: 答对
            answer = chunk.correct_answer
            console.print(f"\n[dim]> {answer}（用户输入正确答案）[/dim]")
            response = engine.receive_answer(answer)
            display_ai_message(response)
            console.print("\n[green]✅ 用户答对，标记为掌握[/green]")

        elif current_idx == 1:
            # Chunk 2: 先答错，再 /direct
            wrong_answer = "我不懂这个"
            console.print(f"\n[dim]> {wrong_answer}（用户输入错误答案）[/dim]")
            response = engine.receive_answer(wrong_answer)
            display_ai_message(response)
            console.print("\n[red]❌ 用户答错，给出提示[/red]")

            # Use /direct
            console.print("\n[dim]> /direct（用户启用速查模式）[/dim]")
            response = engine.receive_answer("", is_direct=True)
            display_ai_message(response)
            console.print("\n[yellow]⚡ 速查模式生效，知识点标记为'待巩固'[/yellow]")

        elif current_idx == 2:
            # Chunk 3: 答对
            answer = chunk.correct_answer
            console.print(f"\n[dim]> {answer}（用户输入正确答案）[/dim]")
            response = engine.receive_answer(answer)
            display_ai_message(response)
            console.print("\n[green]✅ 用户答对，标记为掌握[/green]")

        # Advance
        response = engine.next_chunk()
        current_idx = engine.topic_state.current_chunk_index

        if response.is_final:
            console.print(f"\n[green]{response.content}[/green]")
            break

    # ─── Step 5: Save Progress ───
    print_step(5, "保存学习进度")
    storage.save_topic_state(topic_state.topic_id, topic_state.model_dump(mode="json"))
    if engine.memory.messages:
        storage.save_conversation_history(topic_state.topic_id, engine.memory.messages)
    console.print("[dim]进度已保存到 data/[/dim]")

    # ─── Step 6: Learning Report ───
    print_step(6, "学习报告")
    mastered = sum(1 for c in topic_state.chunks if c.status == LearningStatus.MASTERED)
    needs_review = sum(1 for c in topic_state.chunks if c.status == LearningStatus.NEEDS_REVIEW)
    total = len(topic_state.chunks)
    rate = mastered / total * 100 if total else 0

    console.print(Panel.fit(
        f"[bold green]🎉 学习完成！[/bold green]\n\n"
        f"掌握: [green]{mastered}[/green] / {total}\n"
        f"待巩固: [yellow]{needs_review}[/yellow]\n"
        f"完成率: [cyan]{rate:.0f}%[/cyan]",
        border_style="green"
    ))

    # ─── Step 7: Resume Demo ───
    print_step(7, "进度恢复验证")
    console.print("[dim]模拟重启程序，从保存的进度恢复...[/dim]")

    saved_state = storage.load_topic_state(topic_id)
    if saved_state:
        restored = engine.topic_state.__class__.model_validate(saved_state)
        console.print(f"[green]✅ 恢复成功：当前进度 {restored.current_chunk_index + 1}/{restored.total_chunks}[/green]")
        console.print(f"[dim]  掌握: {sum(1 for c in restored.chunks if c.status == LearningStatus.MASTERED)}[/dim]")
        console.print(f"[dim]  待巩固: {sum(1 for c in restored.chunks if c.status == LearningStatus.NEEDS_REVIEW)}[/dim]")
    else:
        console.print("[red]❌ 恢复失败[/red]")

    console.print("\n[bold cyan]━━━ 演示结束 ━━━[/bold cyan]\n")


if __name__ == "__main__":
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        console.print("[red]请先配置 ANTHROPIC_API_KEY[/red]")
        sys.exit(1)
    main()
