"""Teacher-skill 唯一入口 — 控制 CLI 交互与初始化。"""
import argparse
import os
import sys

# Fix Windows console UTF-8 encoding without replacing pytest capture streams.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

load_dotenv()

from src.core.engine import TutorEngine, TutorState
from src.utils.logger import get_logger
from src.core.memory import ConversationMemory
from src.utils.storage import TopicStorage
from models.protocol import AIMessage, ResponseType
from models.state import TopicState, LearningStatus
from models.user import UserProfile


console = Console()


class TeacherSkillApp:
    """Teacher-skill main application — CLI interaction and lifecycle."""

    def __init__(self):
        from src.utils.config import get_config
        cfg = get_config()
        self.user_id = cfg.app.user_id
        self.storage = TopicStorage(self.user_id)
        self.current_engine: TutorEngine | None = None
        self._llm_available = self._check_llm()
        self.logger = get_logger("main")

    def _check_llm(self) -> bool:
        """Verify that an API key is configured."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and api_key != "your_api_key_here":
            return True
        console.print("[yellow]⚠️ 警告: 未配置 ANTHROPIC_API_KEY，LLM 调用将不可用[/yellow]\n")
        return False

    def start(self) -> bool:
        """Print welcome banner and validate prerequisites."""
        self.logger.info("Application starting")
        console.print(
            Panel.fit(
                "[bold cyan]🎓 Teacher-skill 数字助教[/bold cyan]\n\n"
                "[yellow]启发式学习循环：[/yellow]\n"
                "讲解 → 提问 → 反馈 → 循环\n\n"
                "[dim]输入 /help 查看帮助[/dim]",
                border_style="cyan",
            )
        )
        console.print()

        if not self._llm_available:
            self.logger.error("LLM not available: ANTHROPIC_API_KEY missing")
            console.print("[red]请先配置 ANTHROPIC_API_KEY 再使用[/red]")
            console.print("参考: https://console.anthropic.com/")
            return False
        self.logger.info("LLM available, ready to start")
        return True

    def run(self, file_path: str | None = None) -> None:
        """Main application loop.

        Args:
            file_path: 可选，从文件加载学习材料（.md/.txt/.pdf）。
        """
        try:
            if not self.start():
                return

            user_level = self._run_onboarding()

            if file_path:
                self._start_new_topic(user_level, file_path=file_path)
                return

            selected_topic_id = self._select_topic_or_new()

            if selected_topic_id:
                self._resume_topic(selected_topic_id)
                return

            self._start_new_topic(user_level)
        except Exception as exc:
            self.logger.error(f"Application error: {exc}")
            self._save_progress()
            console.print(f"\n[red]⚠️ 系统遇到了问题: {exc}[/red]")
            console.print("[dim]你的学习进度已自动保存，可以重新启动继续。[/dim]")

    # ─── Onboarding ───

    def _run_onboarding(self) -> str:
        """Run onboarding if no profile exists; return the user's level."""
        profile_data = self.storage.load_user_profile()
        if profile_data and profile_data.get("level"):
            level = profile_data.get("level", "beginner")
            self.logger.info(f"Loaded existing profile, level={level}")
            console.print(f"[dim]当前学习水平：{level}[/dim]\n")
            return level

        self.logger.info("Starting onboarding")
        console.print("[cyan]👋 初次见面，让我先了解一下你的背景...[/cyan]")
        engine = TutorEngine(self.user_id, "onboarding")
        self._display_response(engine.start_onboarding())

        user_input = console.input("\n[bold blue>[/bold blue] ").strip() or "完全从零开始"
        result = engine.process_onboarding_answer(user_input)
        level = result.get("level", "beginner")

        profile = UserProfile(
            user_id=self.user_id,
            level=level,
            familiar_topics=result.get("familiar_topics", []),
        )
        self.storage.save_user_profile(profile.model_dump())

        console.print(f"\n[green]✅ 已根据你的回答设定学习水平：[yellow]{level}[/yellow][/green]")
        if result.get("explanation"):
            console.print(f"[dim]{result['explanation']}[/dim]")
        console.print()
        return level

    # ─── Topic Selection ───

    def _select_topic_or_new(self) -> str | None:
        """Show existing topics and let user choose one or start new.

        Returns the selected topic_id, or None to start a new topic.
        """
        topics = self.storage.list_topics()
        self.logger.info(f"Found {len(topics)} existing topics")
        if not topics:
            return None

        console.print(f"[cyan]📁 发现 {len(topics)} 个进行中的主题[/cyan]")
        for i, t in enumerate(topics, 1):
            state = self.storage.load_topic_state(t)
            if state:
                progress = state.get("current_chunk_index", 0) + 1
                total = state.get("total_chunks", 0)
                status = "已完成" if state.get("is_completed") else "进行中"
                console.print(f"  [{i}] {t}: 进度 {progress}/{total} ({status})")
        console.print()
        console.print("[dim]输入对应数字继续学习，或输入 new 开始新主题[/dim]")

        while True:
            choice = console.input("\n[bold blue>[/bold blue] ").strip()
            if choice.lower() == "new":
                return None
            try:
                idx = int(choice)
                if 1 <= idx <= len(topics):
                    return topics[idx - 1]
                console.print("[red]无效的选择，请重新输入[/red]")
            except ValueError:
                console.print("[red]请输入数字或 new[/red]")

    def _resume_topic(self, topic_id: str) -> None:
        """Resume an existing topic from its saved state."""
        self.logger.info(f"Resuming topic {topic_id}")
        console.print(f"\n[cyan]正在恢复主题：{topic_id}...[/cyan]")
        state_data = self.storage.load_topic_state(topic_id)
        history_data = self.storage.load_conversation_history(topic_id)

        if not state_data:
            self.logger.error(f"Failed to load topic state: {topic_id}")
            console.print("[red]无法加载该主题的学习进度[/red]")
            return

        topic_state = TopicState.model_validate(state_data)
        self.current_engine = TutorEngine(self.user_id, topic_id)

        if history_data and history_data.get("messages"):
            self.current_engine.restore_memory(history_data["messages"])

        if topic_state.is_completed:
            self._show_summary(topic_state)
            return

        self._learning_loop(topic_state)
        self._show_summary(topic_state)

    def _start_new_topic(
        self, user_level: str, file_path: str | None = None
    ) -> None:
        """Start a brand-new topic.

        Args:
            user_level: 用户学习水平。
            file_path: 可选，从文件加载学习材料。
        """
        topic_id = f"topic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"Starting new topic {topic_id}, user_level={user_level}")

        if file_path:
            material = self._load_material_from_file(file_path)
            if material is None:
                return
        else:
            console.print(
                "[cyan]请输入你要学习的内容（可以是文本段落或主题描述）：[/cyan]"
            )
            console.print(
                "[dim]输入 /load <文件路径> 加载 .md/.txt/.pdf，"
                "或直接粘贴文本，输入 /done 结束[/dim]\n"
            )

            first_line = input().strip()
            if first_line.startswith("/load "):
                path = first_line[6:].strip().strip('"').strip("'")
                material = self._load_material_from_file(path)
                if material is None:
                    return
            else:
                lines = [first_line]
                while True:
                    line = input()
                    if line.strip() == "/done":
                        break
                    lines.append(line)
                material = "\n".join(lines).strip()

        if not material:
            console.print("[yellow]未输入内容，退出[/yellow]")
            return

        self.logger.info(f"Received material: {len(material)} chars")
        console.print(f"\n[dim]收到材料 ({len(material)} 字符)，开始分析...[/dim]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[cyan]正在分析材料...", total=None)
            self.current_engine = TutorEngine(self.user_id, topic_id)
            topic_state = self.current_engine.analyze_material(
                material, user_level=user_level
            )

        self.logger.info(f"Material analyzed: {topic_state.total_chunks} chunks")
        self._show_analysis_result(topic_state)
        self._learning_loop(topic_state)
        self._show_summary(topic_state)

    def _load_material_from_file(self, file_path: str) -> str | None:
        """从文件加载学习材料，返回内容或 None（加载失败时）。"""
        from src.utils.file_loader import FileLoadError, load_file

        try:
            material = load_file(file_path)
            self.logger.info(f"Loaded file {file_path}: {len(material)} chars")
            console.print(
                f"[dim]已加载文件 {file_path} ({len(material)} 字符)[/dim]\n"
            )
            return material
        except FileLoadError as exc:
            self.logger.error(f"File load failed: {exc}")
            console.print(f"[red]加载文件失败: {exc}[/red]")
            return None

    # ─── Learning Loop ───

    def _learning_loop(self, topic_state: TopicState) -> None:
        """Run the interactive learning loop for a topic."""
        self.logger.info(f"Learning loop started: {topic_state.total_chunks} chunks")
        response = self.current_engine.start_topic(topic_state)
        self._display_response(response)

        while True:
            user_input = console.input("\n[bold blue>[/bold blue] ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("/help", "help"):
                self._show_help()
                continue

            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                self.logger.info("User requested exit, saving progress")
                self._save_progress()
                console.print("[cyan]已保存进度，下次再见！[/cyan]")
                sys.exit(0)

            if user_input.lower() == "/direct":
                self.logger.info("User used /direct")
                response = self.current_engine.receive_answer("", is_direct=True)
                self._display_response(response)
                if response.is_final and self._advance_or_finish():
                    self.logger.info("Learning loop completed")
                    break
                continue

            if user_input.lower() == "/progress":
                self._show_progress()
                continue

            # Normal answer
            self.logger.debug(f"User answer: {user_input[:50]}...")
            response = self.current_engine.receive_answer(user_input, is_direct=False)
            self._display_response(response)

            if response.response_type == ResponseType.FEEDBACK_CORRECT:
                if self._advance_or_finish():
                    self.logger.info("Learning loop completed")
                    break
            elif response.response_type == ResponseType.EXPLANATION and response.is_final:
                self.logger.info("Learning loop completed")
                break

    def _advance_or_finish(self) -> bool:
        """Move to the next chunk.

        Returns:
            True if the topic is complete, otherwise False.
        """
        response = self.current_engine.next_chunk()
        if response.is_final:
            self._display_response(response)
            return True
        self._display_response(response)
        return False

    # ─── Display ───

    def _display_response(self, response: AIMessage) -> None:
        """Render an AIMessage to the console."""
        console.print()

        match response.response_type:
            case ResponseType.EXPLANATION:
                console.print(f"[cyan]{response.content}[/cyan]")
            case ResponseType.QUESTION:
                console.print(f"[bold yellow]📝 {response.question}[/bold yellow]")
                if response.options:
                    for opt in response.options:
                        console.print(f"  {opt}")
                console.print(f"\n[dim]进度: {self.current_engine.get_progress()}[/dim]")
            case ResponseType.FEEDBACK_CORRECT:
                console.print(f"[green]✅ {response.content}[/green]")
            case ResponseType.FEEDBACK_WRONG | ResponseType.FEEDBACK_HINT:
                console.print(f"[red]❌ {response.content}[/red]")
                if response.hint_level > 0:
                    console.print(f"[dim]提示等级: {response.hint_level}[/dim]")
            case ResponseType.DIRECT_ANSWER:
                console.print(
                    Panel.fit(
                        f"[bold yellow]【速查模式】[/bold yellow]\n\n{response.content}",
                        border_style="yellow",
                    )
                )

    def _show_analysis_result(self, topic_state: TopicState) -> None:
        """Display the result of material analysis."""
        console.print(
            Panel.fit(
                f"[bold green]✅ 材料分析完成！[/bold green]\n\n"
                f"主题：{topic_state.topic_id}\n"
                f"知识点数量：{topic_state.total_chunks} 个",
                border_style="green",
            )
        )

        table = Table(title="📚 知识卡片预览")
        table.add_column("序号", style="cyan", width=4)
        table.add_column("标题", style="white")
        table.add_column("难度", style="yellow", width=8)

        for i, chunk in enumerate(topic_state.chunks):
            table.add_row(str(i + 1), chunk.title or "未命名", chunk.difficulty)

        console.print(table)
        console.print()

    def _show_progress(self) -> None:
        """Display current learning progress."""
        if not self.current_engine or not self.current_engine.topic_state:
            return

        ts = self.current_engine.topic_state
        console.print(
            Panel.fit(
                f"[bold]当前进度[/bold]\n\n"
                f"知识点: {ts.current_chunk_index + 1}/{ts.total_chunks}\n"
                f"状态: {ts.is_completed and '已完成' or '进行中'}",
                border_style="cyan",
            )
        )

    def _show_help(self) -> None:
        """Display available commands."""
        help_text = """
[bold]可用命令：[/bold]

  /help     - 显示此帮助
  /progress - 显示当前进度
  /direct   - 速查模式：直接查看答案（标记为待巩固）
  /load     - 加载文件（在新主题输入阶段使用）
  /exit     - 退出并保存进度

  直接输入回答内容即可答题
"""
        console.print(Panel.fit(help_text, title="帮助", border_style="green"))

    def _show_summary(self, topic_state: TopicState) -> None:
        """Display a learning summary at the end of a topic."""
        mastered = sum(1 for c in topic_state.chunks if c.status == LearningStatus.MASTERED)
        needs_review = sum(1 for c in topic_state.chunks if c.status == LearningStatus.NEEDS_REVIEW)
        total = len(topic_state.chunks)

        rate = mastered / total * 100 if total else 0

        console.print(
            Panel.fit(
                f"[bold green]🎉 学习完成！[/bold green]\n\n"
                f"掌握: [green]{mastered}[/green] / {total}\n"
                f"待巩固: [yellow]{needs_review}[/yellow]\n"
                f"完成率: [cyan]{rate:.0f}%[/cyan]",
                border_style="green",
            )
        )
        self._save_progress()

    def _save_progress(self) -> None:
        """Persist current topic state and conversation history."""
        if not self.current_engine or not self.current_engine.topic_state:
            return

        ts = self.current_engine.topic_state
        self.storage.save_topic_state(ts.topic_id, ts.model_dump(mode="json"))

        if self.current_engine.memory.messages:
            self.storage.save_conversation_history(
                ts.topic_id, self.current_engine.memory.messages
            )
        self.logger.info(f"Progress saved for topic {ts.topic_id}")


def main() -> None:
    """Application entry point."""
    parser = argparse.ArgumentParser(description="🎓 Teacher-skill 数字助教")
    parser.add_argument(
        "--file",
        help="从文件加载学习材料（支持 .md/.txt/.pdf）",
        default=None,
    )
    args = parser.parse_args()

    app = TeacherSkillApp()
    app.run(file_path=args.file)


if __name__ == "__main__":
    main()
