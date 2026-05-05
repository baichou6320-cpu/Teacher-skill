"""Console rendering helpers for the Teacher-skill CLI.

This module intentionally avoids importing runtime model classes so startup
commands such as ``python main.py --check`` can still run before dependencies
like pydantic are installed.
"""
from __future__ import annotations

import builtins
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

try:
    from rich.console import Console
    from rich.markup import escape
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
except ModuleNotFoundError:
    def _strip_markup(value: str) -> str:
        return re.sub(r"\[/?[a-zA-Z][^\]]*\]", "", value)

    def escape(value: object) -> str:
        """Minimal markup escape fallback used before dependencies are installed."""
        return str(value)

    class Console:
        """Small console fallback so startup commands can run without rich."""

        def print(self, *objects, **kwargs) -> None:
            builtins.print(*(_strip_markup(str(obj)) for obj in objects))

        def input(self, prompt: str = "") -> str:
            return builtins.input(prompt)

    class Panel:
        """Fallback Panel that renders plain text."""

        @staticmethod
        def fit(renderable, *args, **kwargs):
            return renderable

    class Table:
        """Fallback Table that renders rows as plain text."""

        def __init__(self, title: str | None = None, *args, **kwargs):
            self.title = title
            self.columns: list[str] = []
            self.rows: list[tuple[str, ...]] = []

        def add_column(self, header: str, *args, **kwargs) -> None:
            self.columns.append(header)

        def add_row(self, *values: object) -> None:
            self.rows.append(tuple(str(value) for value in values))

        def __str__(self) -> str:
            lines: list[str] = []
            if self.title:
                lines.append(self.title)
            if self.columns:
                lines.append(" | ".join(self.columns))
                lines.append("-" * max(8, len(lines[-1])))
            lines.extend(" | ".join(row) for row in self.rows)
            return "\n".join(lines)

    class Progress:
        """No-op fallback for rich Progress."""

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def add_task(self, *args, **kwargs):
            return 0

    class SpinnerColumn:
        pass

    class TextColumn:
        def __init__(self, *args, **kwargs):
            pass


console = Console()


def _enum_value(value: Any) -> str:
    """Return an enum's stored value without importing the enum class."""
    raw = getattr(value, "value", value)
    return "" if raw is None else str(raw)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read a key from either a mapping or a model-like object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def topic_display_title(topic_id: str, state: dict[str, Any]) -> str:
    """Return a readable topic title for history selection."""
    title = str(state.get("title") or "").strip()
    if title:
        return title

    source_path = str(state.get("source_path") or "").strip()
    if source_path:
        stem = Path(source_path).stem.strip()
        if stem:
            return stem

    for chunk in state.get("chunks", []) or []:
        chunk_title = str(chunk.get("title") or "").strip()
        if chunk_title:
            return chunk_title

    return topic_id


def topic_display_summary(state: dict[str, Any]) -> str:
    """Return a short readable topic summary for history selection."""
    summary = str(state.get("summary") or "").strip()
    if summary:
        return summary[:100]

    titles = [
        str(chunk.get("title") or "").strip()
        for chunk in state.get("chunks", []) or []
        if str(chunk.get("title") or "").strip()
    ]
    if titles:
        summary = "、".join(titles[:3])
        if len(titles) > 3:
            summary += " 等"
        return summary[:100]

    return ""


def topic_source_label(state: dict[str, Any] | Any) -> str:
    """Return a readable material source label."""
    source_type = str(_get(state, "source_type", "") or "").strip()
    source_path = str(_get(state, "source_path", "") or "").strip()
    if source_type == "demo":
        return "内置示例"
    if source_path:
        return f"文件 {Path(source_path).name}"
    if source_type == "file":
        return "文件"
    return "手动输入"


def format_topic_time(state: dict[str, Any]) -> str:
    """Format topic timestamp for display."""
    value = state.get("updated_at") or state.get("created_at")
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def format_optional_time(value: datetime | str | None) -> str:
    """Format an optional datetime for compact tables."""
    if not value:
        return "未复习"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def hint_level_label(hint_level: int) -> str:
    """Return a human-readable label for progressive hint levels."""
    labels = {
        1: "线索提示",
        2: "生活类比",
        3: "半解析",
        4: "关键词/部分答案",
    }
    return labels.get(hint_level, "渐进提示")


def format_chunk_status(chunk: Any) -> str:
    """Return a human-readable learning status."""
    status_map = {
        "not_started": "未开始",
        "in_progress": "学习中",
        "mastered": "已掌握",
        "needs_review": "待巩固",
    }
    status = _enum_value(_get(chunk, "status"))
    return status_map.get(status, status)


def display_response(
    response: Any,
    *,
    current_engine: Any,
    supportive_feedback_renderer: Callable[[Any], None],
    output_console: Console = console,
) -> None:
    """Render an AIMessage-like object to the console."""
    output_console.print()
    response_type = _enum_value(_get(response, "response_type"))

    if response_type == "explanation":
        output_console.print(f"[cyan]{_get(response, 'content')}[/cyan]")
        return

    if response_type == "question":
        output_console.print(f"[bold yellow]📝 {_get(response, 'question')}[/bold yellow]")
        options = _get(response, "options")
        if options:
            for opt in options:
                output_console.print(f"  {opt}")
        progress = current_engine.get_progress() if current_engine else "未知"
        output_console.print(f"\n[dim]进度: {progress}[/dim]")
        return

    if response_type == "feedback_correct":
        output_console.print(f"[green]✅ {_get(response, 'content')}[/green]")
        return

    if response_type in ("feedback_wrong", "feedback_hint"):
        supportive_feedback_renderer(response)
        return

    if response_type == "direct_answer":
        output_console.print(
            Panel.fit(
                f"[bold yellow]【速查模式】[/bold yellow]\n\n{_get(response, 'content')}",
                border_style="yellow",
            )
        )


def display_supportive_feedback(response: Any, *, output_console: Console = console) -> None:
    """Render wrong-answer feedback without making the user feel punished."""
    hint_level = max(0, min(int(_get(response, "hint_level", 0) or 0), 4))
    title = "还差一点，我们换个角度试试"
    if hint_level >= 4:
        title = "这一题先放进待巩固，我们保留节奏继续前进"

    details = []
    if hint_level > 0:
        details.append(f"提示层级：第 {hint_level}/4 层（{hint_level_label(hint_level)}）")
    details.append("你可以继续尝试；想先看答案可输入 /direct，系统会标记为待巩固。")

    output_console.print(
        Panel.fit(
            f"[bold yellow]{title}[/bold yellow]\n\n"
            f"{escape(_get(response, 'content'))}\n\n"
            f"[dim]{escape(' · '.join(details))}[/dim]",
            border_style="yellow",
        )
    )


def show_analysis_result(topic_state: Any, *, output_console: Console = console) -> None:
    """Display the result of material analysis."""
    output_console.print(
        Panel.fit(
            f"[bold green]✅ 材料分析完成！[/bold green]\n\n"
            f"主题：{escape(_get(topic_state, 'title') or _get(topic_state, 'topic_id'))}\n"
            f"摘要：{escape(_get(topic_state, 'summary') or '暂无')}\n"
            f"来源：{escape(topic_source_label(topic_state))}\n"
            f"知识点数量：{_get(topic_state, 'total_chunks')} 个",
            border_style="green",
        )
    )

    table = Table(title="📚 知识卡片预览")
    table.add_column("序号", style="cyan", width=4)
    table.add_column("标题", style="white")
    table.add_column("难度", style="yellow", width=8)

    for i, chunk in enumerate(_get(topic_state, "chunks", []) or []):
        table.add_row(str(i + 1), _get(chunk, "title") or "未命名", _get(chunk, "difficulty", ""))

    output_console.print(table)
    output_console.print()


def show_append_result(
    new_chunks: list[Any],
    previous_total: int,
    source_label: str,
    *,
    output_console: Console = console,
) -> None:
    """Display appended chunks and make it clear the current question continues."""
    output_console.print(
        Panel.fit(
            f"[bold green]✅ 已追加材料[/bold green]\n\n"
            f"来源：{source_label}\n"
            f"新增知识点：{len(new_chunks)} 个\n"
            f"当前主题总知识点：{previous_total + len(new_chunks)} 个\n\n"
            "[dim]当前题目不会被打断，答完后会继续进入后续知识点。[/dim]",
            border_style="green",
        )
    )

    table = Table(title="📚 新增知识卡片")
    table.add_column("序号", style="cyan", width=4)
    table.add_column("标题", style="white")
    table.add_column("难度", style="yellow", width=8)

    for i, chunk in enumerate(new_chunks, previous_total + 1):
        table.add_row(str(i), _get(chunk, "title") or "未命名", _get(chunk, "difficulty", ""))

    output_console.print(table)
    output_console.print()


def show_progress(current_engine: Any, *, output_console: Console = console) -> None:
    """Display current learning progress."""
    if not current_engine or not current_engine.topic_state:
        return

    ts = current_engine.topic_state
    chunks = _get(ts, "chunks", []) or []
    mastered = sum(1 for c in chunks if _enum_value(_get(c, "status")) == "mastered")
    needs_review = sum(1 for c in chunks if _enum_value(_get(c, "status")) == "needs_review")
    not_started = sum(1 for c in chunks if _enum_value(_get(c, "status")) == "not_started")
    attempts = sum(int(_get(c, "attempts", 0) or 0) for c in chunks)
    wrong = sum(int(_get(c, "fail_count", 0) or 0) for c in chunks)
    current_index = int(_get(ts, "current_chunk_index", 0) or 0)
    current = chunks[current_index] if chunks and current_index < len(chunks) else None
    review_progress = (
        current_engine.get_review_progress()
        if hasattr(current_engine, "get_review_progress")
        else "未开始"
    )
    review_line = (
        f"\n复习进度: [cyan]{review_progress}[/cyan]"
        if review_progress != "未开始"
        else ""
    )
    output_console.print(
        Panel.fit(
            f"[bold]当前进度[/bold]\n\n"
            f"知识点: {current_index + 1}/{_get(ts, 'total_chunks')}\n"
            f"当前: {_get(current, 'title') if current else '无'}\n"
            f"已掌握: [green]{mastered}[/green]\n"
            f"待巩固: [yellow]{needs_review}[/yellow]\n"
            f"未开始: {not_started}\n"
            f"本主题作答: {attempts} 次，答错: {wrong} 次\n"
            f"状态: {_get(ts, 'is_completed') and '已完成' or '进行中'}"
            f"{review_line}",
            border_style="cyan",
        )
    )


def show_chunk_list(current_engine: Any, *, output_console: Console = console) -> None:
    """Display all chunks in the current topic."""
    if not current_engine or not current_engine.topic_state:
        output_console.print("[yellow]当前没有进行中的学习主题[/yellow]")
        return

    ts = current_engine.topic_state
    table = Table(title="📚 知识点列表")
    table.add_column("当前", width=4)
    table.add_column("序号", style="cyan", width=4)
    table.add_column("标题", style="white")
    table.add_column("状态", style="yellow", width=8)
    table.add_column("答错", width=6)
    table.add_column("提示", width=6)

    for i, chunk in enumerate(_get(ts, "chunks", []) or [], 1):
        table.add_row(
            "→" if i - 1 == _get(ts, "current_chunk_index", 0) else "",
            str(i),
            _get(chunk, "title") or "未命名",
            format_chunk_status(chunk),
            str(_get(chunk, "fail_count", 0)),
            str(_get(chunk, "hint_level", 0)),
        )

    output_console.print(table)
    output_console.print("[dim]可用 /jump <序号> 跳转到指定知识点。[/dim]")


def show_review_items(current_engine: Any, *, output_console: Console = console) -> None:
    """Display chunks that need review."""
    if not current_engine or not current_engine.topic_state:
        output_console.print("[yellow]当前没有进行中的学习主题[/yellow]")
        return

    ts = current_engine.topic_state
    review_items = [
        (i, chunk)
        for i, chunk in enumerate(_get(ts, "chunks", []) or [], 1)
        if _enum_value(_get(chunk, "status")) == "needs_review"
        or int(_get(chunk, "fail_count", 0) or 0) > 0
        or int(_get(chunk, "hint_level", 0) or 0) > 0
    ]

    if not review_items:
        output_console.print("[green]当前没有待巩固知识点。[/green]")
        return

    table = Table(title="🟡 待巩固知识点")
    table.add_column("序号", style="cyan", width=4)
    table.add_column("标题", style="white")
    table.add_column("状态", style="yellow", width=8)
    table.add_column("答错", width=6)
    table.add_column("提示", width=6)

    for i, chunk in review_items:
        table.add_row(
            str(i),
            _get(chunk, "title") or "未命名",
            format_chunk_status(chunk),
            str(_get(chunk, "fail_count", 0)),
            str(_get(chunk, "hint_level", 0)),
        )

    output_console.print(table)
    output_console.print("[dim]可用 /jump <序号> 回到对应知识点。[/dim]")


def show_history_topics(profile: Any, *, output_console: Console = console) -> None:
    """Display archived learning topics from the user profile."""
    history_topics = _get(profile, "history_topics", []) or []
    if not history_topics:
        output_console.print("[yellow]还没有历史学习记录。完成一个主题后会自动归档到这里。[/yellow]")
        return

    table = Table(title="📚 历史学习记录")
    table.add_column("序号", style="cyan", width=4)
    table.add_column("主题", style="white")
    table.add_column("掌握", style="green", width=8)
    table.add_column("待巩固", style="yellow", width=8)
    table.add_column("完成时间", style="dim", width=16)
    table.add_column("上次复习", style="dim", width=16)

    for i, topic in enumerate(history_topics, 1):
        table.add_row(
            str(i),
            escape(_get(topic, "title") or _get(topic, "topic_id")),
            f"{_get(topic, 'mastered_chunks')}/{_get(topic, 'total_chunks')}",
            str(_get(topic, "review_chunks")),
            format_optional_time(_get(topic, "completed_at")),
            format_optional_time(_get(topic, "last_reviewed_at")),
        )

    output_console.print(table)
    output_console.print("[dim]后续复习模式会优先使用这些历史记录和待巩固知识点。[/dim]")


def show_help(*, output_console: Console = console) -> None:
    """Display available commands."""
    help_text = """
[bold]可用命令：[/bold]

  /help     - 显示此帮助
  /progress - 显示当前进度、掌握数、待巩固数和答题统计
  /list     - 查看全部知识点
  /review   - 查看待巩固知识点
  /history  - 查看已归档的历史学习主题
  /skip     - 跳过当前知识点，并标记为待巩固
  /back     - 回到上一个知识点
  /jump N   - 跳到第 N 个知识点，例如 /jump 3
  /direct   - 速查模式：直接查看答案（标记为待巩固）
  /load     - 加载文件；学习中使用会追加为新的知识点
  /exit     - 退出并保存进度

  快速体验：python main.py --demo
  文件学习：python main.py --file article.md
  复习入口：在主题选择时输入“复习一下 主题名”
  直接输入回答内容即可答题
"""
    output_console.print(Panel.fit(help_text, title="帮助", border_style="green"))


def show_summary(topic_state: Any, *, output_console: Console = console) -> tuple[int, int, int]:
    """Display a learning summary and return mastered/review/total counts."""
    chunks = _get(topic_state, "chunks", []) or []
    mastered = sum(1 for c in chunks if _enum_value(_get(c, "status")) == "mastered")
    needs_review = sum(1 for c in chunks if _enum_value(_get(c, "status")) == "needs_review")
    total = len(chunks)
    rate = mastered / total * 100 if total else 0

    output_console.print(
        Panel.fit(
            f"[bold green]🎉 学习完成！[/bold green]\n\n"
            f"主题: [cyan]{escape(_get(topic_state, 'title') or _get(topic_state, 'topic_id'))}[/cyan]\n"
            f"掌握: [green]{mastered}[/green] / {total}\n"
            f"待巩固: [yellow]{needs_review}[/yellow]\n"
            f"完成率: [cyan]{rate:.0f}%[/cyan]",
            border_style="green",
        )
    )
    return mastered, needs_review, total


def show_review_summary(
    topic_state: Any,
    review_stats: dict[str, int],
    remaining_review: list[tuple[int, Any]],
    *,
    output_console: Console = console,
) -> None:
    """Display a review-session summary report."""
    chunks = _get(topic_state, "chunks", []) or []
    total = len(chunks)
    mastered = sum(1 for c in chunks if _enum_value(_get(c, "status")) == "mastered")
    correct_rate = (
        review_stats["correct"] / review_stats["answered"] * 100
        if review_stats["answered"]
        else 0
    )

    output_console.print(
        Panel.fit(
            f"[bold green]✅ 本轮复习完成[/bold green]\n\n"
            f"主题: [cyan]{escape(_get(topic_state, 'title') or _get(topic_state, 'topic_id'))}[/cyan]\n"
            f"当前掌握: [green]{mastered}[/green] / {total}\n"
            f"仍待巩固: [yellow]{len(remaining_review)}[/yellow]\n"
            f"本轮作答: {review_stats['answered']} 次\n"
            f"答对: [green]{review_stats['correct']}[/green]"
            f"（正确率 {correct_rate:.0f}%）\n"
            f"速查: {review_stats['direct']} 次\n"
            f"跳过: {review_stats['skipped']} 次\n"
            f"本轮保留待巩固: [yellow]{review_stats['kept_review']}[/yellow]",
            border_style="green",
        )
    )

    if not remaining_review:
        output_console.print("[green]这轮复习后没有仍需巩固的知识点。[/green]")
        return

    table = Table(title="🟡 复习后仍待巩固")
    table.add_column("序号", style="cyan", width=4)
    table.add_column("标题", style="white")
    table.add_column("状态", style="yellow", width=8)
    table.add_column("答错", width=6)
    table.add_column("提示", width=6)

    for i, chunk in remaining_review[:8]:
        table.add_row(
            str(i),
            escape(_get(chunk, "title") or "未命名"),
            format_chunk_status(chunk),
            str(_get(chunk, "fail_count", 0)),
            str(_get(chunk, "hint_level", 0)),
        )

    output_console.print(table)
    if len(remaining_review) > 8:
        output_console.print(f"[dim]还有 {len(remaining_review) - 8} 个待巩固知识点未显示。[/dim]")

