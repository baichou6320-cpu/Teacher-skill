"""Teacher-skill 唯一入口 — 控制 CLI 交互与初始化。"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Mapping

from src.cli import display as cli_display
from src.cli import environment as cli_environment
from src.cli import review as cli_review

# Fix Windows console UTF-8 encoding without replacing pytest capture streams.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs) -> bool:
        """Fallback when python-dotenv is not installed yet."""
        return False

load_dotenv()

console = cli_display.console
escape = cli_display.escape
Panel = cli_display.Panel
Table = cli_display.Table
Progress = cli_display.Progress
SpinnerColumn = cli_display.SpinnerColumn
TextColumn = cli_display.TextColumn
DEMO_MATERIAL_PATH = Path(__file__).resolve().parent / "samples" / "demo_article.md"
PROJECT_ROOT = Path(__file__).resolve().parent
_RUNTIME_DEPENDENCIES_LOADED = False


def load_runtime_dependencies() -> None:
    """Load non-stdlib modules needed for the actual learning runtime."""
    global _RUNTIME_DEPENDENCIES_LOADED
    global TutorEngine, TutorState, get_logger, ConversationMemory
    global is_review_intent, match_history_topic, TopicStorage
    global AIMessage, ResponseType, ChunkState, TopicState, LearningStatus
    global LearnedTopic, UserProfile

    if _RUNTIME_DEPENDENCIES_LOADED:
        return

    from src.core.engine import TutorEngine, TutorState
    from src.utils.logger import get_logger
    from src.core.memory import ConversationMemory
    from src.core.router import is_review_intent, match_history_topic
    from src.utils.storage import TopicStorage
    from models.protocol import AIMessage, ResponseType
    from models.state import ChunkState, TopicState, LearningStatus
    from models.user import LearnedTopic, UserProfile

    _RUNTIME_DEPENDENCIES_LOADED = True


def collect_environment_checks(
    env: Mapping[str, str] | None = None,
    project_root: Path | None = None,
) -> tuple[list[dict[str, object]], bool]:
    """Collect startup checks without entering the learning flow."""
    return cli_environment.collect_environment_checks(
        env=env,
        project_root=project_root or PROJECT_ROOT,
    )


def _read_env_file_value(env_file: Path, key: str) -> str:
    """Read one simple KEY=value entry from .env without python-dotenv."""
    return cli_environment.read_env_file_value(env_file, key)


def inspect_config_file(project_root: Path | None = None) -> dict[str, object]:
    """Inspect config.yaml, falling back to a stdlib parser if deps are missing."""
    return cli_environment.inspect_config_file(project_root or PROJECT_ROOT)


def initialize_project(
    project_root: Path | None = None,
) -> tuple[list[dict[str, str]], bool]:
    """Prepare first-run local files without requiring runtime dependencies."""
    return cli_environment.initialize_project(project_root or PROJECT_ROOT)


def _read_runtime_dirs_from_config(project_root: Path) -> tuple[Path, Path]:
    """Read data/log dirs from config.yaml with a tiny stdlib parser."""
    return cli_environment.read_runtime_dirs_from_config(project_root)


def _read_simple_yaml_sections(config_path: Path) -> dict[str, dict[str, str]]:
    """Read simple top-level YAML sections containing scalar key/value pairs."""
    return cli_environment.read_simple_yaml_sections(config_path)


def _resolve_project_path(project_root: Path, value: str) -> Path:
    """Resolve config paths relative to the project root."""
    return cli_environment.resolve_project_path(project_root, value)


def _format_project_path(project_root: Path, path: Path) -> str:
    """Format paths relative to the project root when possible."""
    return cli_environment.format_project_path(project_root, path)


def run_project_init() -> bool:
    """Render first-run initialization actions."""
    return cli_environment.render_project_init(
        PROJECT_ROOT,
        output_console=console,
        table_cls=Table,
        panel_cls=Panel,
    )


def run_setup_wizard() -> bool:
    """Render the first-time model/provider setup wizard."""
    return cli_environment.render_setup_wizard(
        PROJECT_ROOT,
        output_console=console,
        table_cls=Table,
        panel_cls=Panel,
    )


def run_environment_check() -> bool:
    """Render environment checks and return whether the app can start."""
    return cli_environment.render_environment_check(
        PROJECT_ROOT,
        output_console=console,
        table_cls=Table,
        panel_cls=Panel,
    )


class TeacherSkillApp:
    """Teacher-skill main application — CLI interaction and lifecycle."""

    def __init__(self):
        load_runtime_dependencies()
        from src.utils.config import get_config
        cfg = get_config()
        self.user_id = cfg.app.user_id
        self.storage = TopicStorage(self.user_id)
        self.current_engine: TutorEngine | None = None
        self.user_level = "beginner"
        self._pending_review_topic_id: str | None = None
        self._llm_available = self._check_llm()
        self.logger = get_logger("main")

    def _check_llm(self) -> bool:
        """Verify that an API key is configured."""
        api_key = (
            os.getenv("TEACHER_SKILL_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("MOONSHOT_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or ""
        )
        if api_key and api_key != "your_api_key_here":
            return True
        console.print("[yellow]⚠️ 警告: 未配置 API Key，LLM 调用将不可用[/yellow]\n")
        console.print("[dim]运行 python main.py --setup 进行配置[/dim]\n")
        return False

    def start(self) -> bool:
        """Print welcome banner and validate prerequisites."""
        self.logger.info("Application starting")
        console.print(
            Panel.fit(
                "[bold cyan]🎓 Teacher-skill 数字助教[/bold cyan]\n\n"
                "[yellow]启发式学习循环：[/yellow]\n"
                "讲解 → 提问 → 反馈 → 循环\n\n"
                "[dim]快速体验：python main.py --demo[/dim]\n"
                "[dim]文件学习：python main.py --file article.md[/dim]\n"
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

    def run(self, file_path: str | None = None, demo: bool = False) -> None:
        """Main application loop.

        Args:
            file_path: 可选，从文件加载学习材料（.md/.txt/.pdf）。
            demo: 是否使用内置示例材料启动体验。
        """
        try:
            if not self.start():
                return

            user_level = self._run_onboarding()
            self.user_level = user_level

            if demo:
                self._start_demo_topic(user_level)
                return

            if file_path:
                self._start_new_topic(user_level, file_path=file_path)
                return

            selected_topic_id = self._select_topic_or_new()

            if selected_topic_id:
                if self._pending_review_topic_id == selected_topic_id:
                    self._review_topic(selected_topic_id)
                    return
                self._resume_topic(selected_topic_id)
                return

            self._start_new_topic(user_level)
        except Exception as exc:
            self.logger.error(f"Application error: {exc}")
            self._save_progress()
            console.print(f"\n[red]⚠️ 系统遇到了问题: {escape(exc)}[/red]")
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

        level = "beginner"
        explanation = ""
        familiar_topics: list[str] = []

        while True:
            user_input = console.input("\n[bold blue]>[/bold blue] ").strip() or "完全从零开始"

            # 如果回答太短，追问一次，让用户多说一点
            if len(user_input.strip()) < 6:
                console.print(
                    "[yellow]你的回答比较简单，能再多说一点吗？"
                    "比如你想学习什么领域，之前有没有接触过？[/yellow]"
                )
                continue

            result = engine.process_onboarding_answer(user_input)

            # LLM 返回的是对话文本（用户在闲聊/无关），显示后继续对话
            if result.get("is_conversation"):
                console.print(f"[cyan]{escape(result['explanation'])}[/cyan]")
                continue

            # 正常判定或离线推断
            level = result.get("level", "beginner")
            explanation = result.get("explanation", "")
            familiar_topics = result.get("familiar_topics", [])
            break

        # 如果走的是 LLM 失败后的离线推断，让用户手动确认或选择
        if "离线推断" in explanation:
            console.print(
                "\n[yellow]⚠️ AI 分析服务暂时不可用，进入离线模式。[/yellow]"
            )
            console.print(
                "[dim]请根据你的实际情况选择学习水平：[/dim]\n"
                "  1. 完全从零开始（beginner）\n"
                "  2. 有一些了解（intermediate）\n"
                "  3. 很熟悉，能深入讨论（advanced）\n"
            )
            choice = (
                console.input("[bold blue]请选择（1/2/3，回车默认 1）：[/bold blue] ")
                .strip() or "1"
            )
            level_map = {"1": "beginner", "2": "intermediate", "3": "advanced"}
            level = level_map.get(choice, "beginner")
            explanation = "你手动选择了学习水平"

        profile = UserProfile(
            user_id=self.user_id,
            level=level,
            familiar_topics=familiar_topics,
        )
        self.storage.save_user_profile(profile.model_dump())

        console.print(f"\n[green]✅ 已根据你的回答设定学习水平：[yellow]{level}[/yellow][/green]")
        if explanation:
            console.print(f"[dim]{explanation}[/dim]")
        console.print()
        return level

    # ─── Topic Selection ───

    def _select_topic_or_new(self) -> str | None:
        """Show existing topics and let user choose one or start new.

        Returns the selected topic_id, or None to start a new topic.
        """
        topic_rows = [
            (topic_id, self.storage.load_topic_state(topic_id) or {})
            for topic_id in self.storage.list_topics()
        ]
        topic_rows.sort(
            key=lambda row: row[1].get("updated_at")
            or row[1].get("created_at")
            or "",
            reverse=True,
        )
        self.logger.info(f"Found {len(topic_rows)} existing topics")
        if not topic_rows:
            return None

        console.print(f"[cyan]📁 发现 {len(topic_rows)} 个进行中的主题[/cyan]")
        for i, (topic_id, state) in enumerate(topic_rows, 1):
            title = self._topic_display_title(topic_id, state)
            total = state.get("total_chunks", 0)
            current_index = state.get("current_chunk_index", 0)
            progress = min(current_index + 1, total) if total else 0
            status = "已完成" if state.get("is_completed") else "进行中"
            updated = self._format_topic_time(state)
            source = self._topic_source_label(state)
            console.print(
                f"  [{i}] [bold]{escape(title)}[/bold]: 进度 {progress}/{total} ({status})"
            )

            summary = self._topic_display_summary(state)
            details = [f"ID: {topic_id}", f"来源: {source}"]
            if updated:
                details.append(f"更新: {updated}")
            if summary:
                details.insert(0, summary)
            console.print(f"      [dim]{escape(' · '.join(details))}[/dim]")
        console.print()
        console.print(
            "[dim]输入对应数字继续学习，输入 new 开始新主题，输入 history 查看历史记录，"
            "或直接说“复习一下 xxx”。[/dim]"
        )
        topic_ids = {topic_id for topic_id, _ in topic_rows}

        while True:
            choice = console.input("\n[bold blue]>[/bold blue] ").strip()
            if choice.lower() == "new":
                return None
            if choice.lower() == "history":
                self._show_history_topics()
                continue
            if is_review_intent(choice):
                matched_topic = self._match_review_topic(choice)
                if matched_topic and matched_topic.topic_id in topic_ids:
                    self._pending_review_topic_id = matched_topic.topic_id
                    console.print(
                        f"[cyan]已匹配历史主题：{escape(matched_topic.title or matched_topic.topic_id)}[/cyan]"
                    )
                    console.print("[dim]进入复习模式：跳过讲解，直接从待巩固知识点开始提问。[/dim]")
                    return matched_topic.topic_id
                if matched_topic:
                    console.print(
                        "[yellow]找到了历史记录，但本地 topic 状态文件不存在，暂时无法恢复。[/yellow]"
                    )
                else:
                    console.print("[yellow]没有匹配到历史主题。可输入 history 查看历史记录。[/yellow]")
                continue
            try:
                idx = int(choice)
                if 1 <= idx <= len(topic_rows):
                    return topic_rows[idx - 1][0]
                console.print("[red]无效的选择，请重新输入[/red]")
            except ValueError:
                console.print("[red]请输入数字、new、history，或“复习一下 xxx”[/red]")

    def _topic_display_title(self, topic_id: str, state: dict) -> str:
        """Return a readable topic title for history selection."""
        return cli_display.topic_display_title(topic_id, state)

    def _topic_display_summary(self, state: dict) -> str:
        """Return a short readable topic summary for history selection."""
        return cli_display.topic_display_summary(state)

    def _topic_source_label(self, state: dict) -> str:
        """Return a readable material source label."""
        return cli_display.topic_source_label(state)

    def _format_topic_time(self, state: dict) -> str:
        """Format topic timestamp for display."""
        return cli_display.format_topic_time(state)

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
        console.print(f"[dim]主题：{escape(topic_state.title or topic_id)}[/dim]")
        self.current_engine = TutorEngine(self.user_id, topic_id)

        if history_data and history_data.get("messages"):
            self.current_engine.restore_memory(history_data["messages"])

        if topic_state.is_completed:
            self._show_summary(topic_state)
            return

        self._learning_loop(topic_state)
        self._show_summary(topic_state)

    def _review_topic(self, topic_id: str) -> None:
        """Start review mode for a previously learned topic."""
        return cli_review.review_topic(
            self,
            topic_id,
            engine_factory=TutorEngine,
            topic_state_model=TopicState,
            output_console=console,
            panel_cls=Panel,
            escape_func=escape,
        )

    def _start_new_topic(
        self,
        user_level: str,
        file_path: str | None = None,
        material: str | None = None,
        source_type: str | None = None,
    ) -> None:
        """Start a brand-new topic.

        Args:
            user_level: 用户学习水平。
            file_path: 可选，从文件加载学习材料。
            material: 可选，直接传入学习材料。
            source_type: 可选，材料来源类型。
        """
        topic_id = f"topic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"Starting new topic {topic_id}, user_level={user_level}")

        if material is None:
            if file_path:
                material = self._load_material_from_file(file_path)
                if material is None:
                    return
            else:
                material = self._collect_material_interactively()
                if material is None:
                    return

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
            self._apply_topic_metadata(
                topic_state,
                material,
                source_path=file_path,
                source_type=source_type,
            )

        self.logger.info(f"Material analyzed: {topic_state.total_chunks} chunks")
        self._show_analysis_result(topic_state)
        self._learning_loop(topic_state)
        self._show_summary(topic_state)

    def _start_demo_topic(self, user_level: str) -> None:
        """Start a new topic from the built-in demo material."""
        material = self._load_demo_material()
        if not material:
            return

        console.print(
            Panel.fit(
                "[bold cyan]Demo 示例模式[/bold cyan]\n\n"
                "将使用内置短文《番茄工作法入门》体验完整学习闭环。\n"
                "[dim]这个模式不需要你准备学习材料，但仍需要可用的 LLM API Key。[/dim]",
                border_style="cyan",
            )
        )
        self._start_new_topic(user_level, material=material, source_type="demo")

    def _load_demo_material(self) -> str | None:
        """Load the built-in demo article."""
        try:
            material = DEMO_MATERIAL_PATH.read_text(encoding="utf-8").strip()
        except OSError as exc:
            self.logger.error(f"Demo material load failed: {exc}")
            console.print(f"[red]加载内置示例失败: {exc}[/red]")
            return None

        self.logger.info(f"Loaded demo material: {len(material)} chars")
        return material

    def _apply_topic_metadata(
        self,
        topic_state: TopicState,
        material: str,
        source_path: str | None = None,
        source_type: str | None = None,
    ) -> None:
        """Fill missing human-readable topic metadata."""
        if source_type:
            topic_state.source_type = source_type
            topic_state.source_path = source_path
        elif source_path:
            topic_state.source_type = "file"
            topic_state.source_path = source_path
        else:
            topic_state.source_type = "manual"
            topic_state.source_path = None

        topic_state.material_chars = len(material)

        if not topic_state.title:
            topic_state.title = self._infer_topic_title(topic_state, material, source_path)
        if not topic_state.summary:
            topic_state.summary = self._infer_topic_summary(topic_state, material)
        topic_state.updated_at = datetime.now()

    def _infer_topic_title(
        self,
        topic_state: TopicState,
        material: str,
        source_path: str | None = None,
    ) -> str:
        """Infer a readable topic title without an extra LLM call."""
        if source_path:
            stem = Path(source_path).stem.strip()
            if stem:
                return stem[:40]

        first_chunk_title = next(
            (chunk.title.strip() for chunk in topic_state.chunks if chunk.title.strip()),
            "",
        )
        if first_chunk_title:
            return first_chunk_title[:40]

        first_line = next(
            (line.strip() for line in material.splitlines() if line.strip()),
            "",
        )
        if first_line:
            return first_line[:40]

        return topic_state.topic_id

    def _infer_topic_summary(self, topic_state: TopicState, material: str) -> str:
        """Infer a short topic summary from chunks or material."""
        titles = [chunk.title.strip() for chunk in topic_state.chunks if chunk.title.strip()]
        if titles:
            summary = "、".join(titles[:3])
            if len(titles) > 3:
                summary += " 等"
            return summary[:100]

        first_line = next(
            (line.strip() for line in material.splitlines() if line.strip()),
            "",
        )
        return first_line[:100]

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

    def _parse_load_command(self, user_input: str) -> str | None:
        """Return the path from a /load command, or None if it is not /load."""
        parts = user_input.strip().split(maxsplit=1)
        if not parts or parts[0].lower() != "/load":
            return None
        if len(parts) == 1:
            return ""
        return parts[1].strip().strip('"').strip("'")

    def _collect_material_interactively(self) -> str | None:
        """Collect material for a new topic without forcing /done by default."""
        console.print("[cyan]请选择学习材料来源：[/cyan]")
        console.print("[bold]快速体验：[/bold]如果还没有材料，可以退出后运行：")
        console.print("  [green]python main.py --demo[/green]")
        console.print("[bold]推荐：[/bold]先把材料保存成文件，然后运行：")
        console.print("  [green]python main.py --file article.md[/green]\n")
        console.print(
            "[dim]当前也可以输入 /load <文件路径> 加载 .md/.txt/.pdf；"
            "直接输入一段文字会立即开始分析。[/dim]"
        )
        console.print(
            "[dim]只有在需要粘贴多行文本时，才输入 /paste 进入多行模式，"
            "再用 /done 结束。[/dim]\n"
        )

        while True:
            user_input = console.input("[bold blue]材料>[/bold blue] ").strip()
            if not user_input:
                continue

            load_path = self._parse_load_command(user_input)
            if load_path is not None:
                if not load_path:
                    console.print("[yellow]用法：/load <文件路径>[/yellow]")
                    continue
                material = self._load_material_from_file(load_path)
                if material is None:
                    continue
                return material

            lowered = user_input.lower()
            if lowered in ("/exit", "/quit", "exit", "quit"):
                console.print("[cyan]已取消新主题创建[/cyan]")
                return None

            if lowered == "/paste":
                return self._read_multiline_material()

            if lowered == "/done":
                console.print("[yellow]现在不需要先输入 /done。请先输入材料，或使用 /load <文件路径>。[/yellow]")
                continue

            console.print(
                f"[dim]已收到单行材料 ({len(user_input)} 字符)。"
                "长文档推荐使用 --file 或 /load。[/dim]\n"
            )
            return user_input

    def _read_multiline_material(self) -> str | None:
        """Read multiline pasted material until /done."""
        console.print("[cyan]进入多行粘贴模式。粘贴完成后单独输入 /done。[/cyan]")
        console.print("[dim]输入 /cancel 可取消本次输入。[/dim]\n")

        lines: list[str] = []
        while True:
            line = input()
            command = line.strip().lower()
            if command == "/done":
                material = "\n".join(lines).strip()
                if not material:
                    console.print("[yellow]没有收到任何材料[/yellow]")
                    return None
                return material
            if command == "/cancel":
                console.print("[cyan]已取消多行输入[/cyan]")
                return None
            lines.append(line)

    def _append_material_from_file(self, file_path: str) -> bool:
        """Load a file and append its analyzed chunks to the current topic."""
        material = self._load_material_from_file(file_path)
        if material is None:
            return False
        return self._append_material(material, source_label=file_path)

    def _append_material(self, material: str, source_label: str = "手动输入") -> bool:
        """Append material to the current topic without interrupting the current question."""
        if not self.current_engine or not self.current_engine.topic_state:
            console.print("[yellow]当前没有进行中的主题，无法追加材料[/yellow]")
            return False

        previous_total = self.current_engine.topic_state.total_chunks
        console.print(
            f"\n[dim]正在追加材料：{source_label} ({len(material)} 字符)...[/dim]\n"
        )

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("[cyan]正在分析追加材料...", total=None)
                new_chunks = self.current_engine.append_material(
                    material,
                    user_level=getattr(self, "user_level", "beginner"),
                )
        except Exception as exc:
            self.logger.error(f"Append material failed: {exc}")
            console.print(f"[red]追加材料失败: {exc}[/red]")
            console.print("[dim]当前题目没有被修改，可以继续作答。[/dim]")
            return False

        if not new_chunks:
            console.print("[yellow]追加材料没有产生新的知识点[/yellow]")
            return False

        self._show_append_result(new_chunks, previous_total, source_label)
        self._save_progress()
        return True

    # ─── Learning Loop ───

    def _learning_loop(self, topic_state: TopicState) -> None:
        """Run the interactive learning loop for a topic."""
        self.logger.info(f"Learning loop started: {topic_state.total_chunks} chunks")
        response = self.current_engine.start_topic(topic_state)
        self._display_response(response)

        while True:
            user_input = console.input("\n[bold blue]>[/bold blue] ").strip()

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

            if user_input.lower() == "/skip":
                if self._handle_skip():
                    self.logger.info("Learning loop completed")
                    break
                continue

            if user_input.lower() == "/back":
                self._handle_back()
                continue

            if user_input.lower() == "/list":
                self._show_chunk_list()
                continue

            if user_input.lower() == "/review":
                self._show_review_items()
                continue

            if user_input.lower() == "/history":
                self._show_history_topics()
                continue

            if self._handle_jump_command(user_input):
                continue

            load_path = self._parse_load_command(user_input)
            if load_path is not None:
                if not load_path:
                    console.print("[yellow]用法：/load <文件路径>[/yellow]")
                    continue
                self._append_material_from_file(load_path)
                continue

            # Normal answer
            confirmed_answer = self._confirm_answer_submission(user_input)
            if confirmed_answer is None:
                continue

            self.logger.debug(f"User answer: {confirmed_answer[:50]}...")
            response = self.current_engine.receive_answer(confirmed_answer, is_direct=False)
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

    def _review_loop(self, topic_state: TopicState) -> None:
        """Run review mode without re-teaching each chunk."""
        return cli_review.run_review_loop(
            self,
            topic_state,
            output_console=console,
            sys_module=sys,
        )

    def _new_review_stats(self) -> dict[str, int]:
        """Create counters for one review session."""
        return cli_review.new_review_stats()

    def _record_review_result(
        self,
        stats: dict[str, int],
        response: AIMessage,
        *,
        is_direct: bool = False,
        is_skipped: bool = False,
    ) -> None:
        """Update review-session counters from one user action."""
        return cli_review.record_review_result(
            stats,
            response,
            is_direct=is_direct,
            is_skipped=is_skipped,
        )

    def _review_response_finishes_item(self, response: AIMessage) -> bool:
        """Return whether a review response should move to the next review item."""
        return cli_review.review_response_finishes_item(response)

    def _advance_review_or_finish(self) -> bool:
        """Move to the next review item.

        Returns True when the review queue is complete.
        """
        return cli_review.advance_review_or_finish(self)

    def _finish_review_session(
        self,
        topic_state: TopicState,
        review_stats: dict[str, int],
    ) -> None:
        """Show review summary and persist review metadata."""
        return cli_review.finish_review_session(self, topic_state, review_stats)

    def _confirm_answer_submission(self, answer: str) -> str | None:
        """Ask the user to confirm, edit, or cancel an answer before judging."""
        current_answer = answer.strip()
        while True:
            console.print(
                Panel.fit(
                    "[bold]确认提交这次回答？[/bold]\n\n"
                    f"{escape(current_answer)}\n\n"
                    "[dim]按 Enter 提交，输入 /edit 修改，输入 /cancel 取消。[/dim]",
                    border_style="blue",
                )
            )
            choice = console.input("[bold blue]确认>[/bold blue] ").strip()
            if not choice:
                return current_answer

            lowered = choice.lower()
            if lowered == "/cancel":
                console.print("[cyan]已取消本次回答，可以重新输入。[/cyan]")
                return None

            if lowered == "/edit":
                edited = console.input("[bold blue]修改回答>[/bold blue] ").strip()
                if not edited:
                    console.print("[yellow]修改内容为空，保留原回答。[/yellow]")
                    continue
                current_answer = edited
                continue

            console.print("[yellow]请按 Enter 提交，或输入 /edit、/cancel。[/yellow]")

    def _handle_skip(self) -> bool:
        """Skip the current chunk and continue or finish."""
        if not self.current_engine or not self.current_engine.topic_state:
            console.print("[yellow]当前没有进行中的学习主题[/yellow]")
            return False

        response = self.current_engine.skip_current_chunk()
        self._display_response(response)
        self._save_progress()
        return response.is_final

    def _handle_back(self) -> None:
        """Move back to the previous chunk."""
        if not self.current_engine or not self.current_engine.topic_state:
            console.print("[yellow]当前没有进行中的学习主题[/yellow]")
            return

        response = self.current_engine.previous_chunk()
        self._display_response(response)
        self._save_progress()

    def _handle_jump_command(self, user_input: str) -> bool:
        """Handle /jump commands.

        Returns True when the input was a /jump command, even if invalid.
        """
        parts = user_input.strip().split(maxsplit=1)
        if not parts or parts[0].lower() != "/jump":
            return False

        if len(parts) != 2 or not parts[1].strip().isdigit():
            console.print("[yellow]用法：/jump <知识点编号>，例如 /jump 3[/yellow]")
            return True

        if not self.current_engine or not self.current_engine.topic_state:
            console.print("[yellow]当前没有进行中的学习主题[/yellow]")
            return True

        chunk_number = int(parts[1].strip())
        try:
            response = self.current_engine.jump_to_chunk(chunk_number)
        except ValueError as exc:
            console.print(f"[yellow]{exc}[/yellow]")
            return True

        self._display_response(response)
        self._save_progress()
        return True

    # ─── Display ───

    def _display_response(self, response: AIMessage) -> None:
        """Render an AIMessage to the console."""
        return cli_display.display_response(
            response,
            current_engine=self.current_engine,
            supportive_feedback_renderer=self._display_supportive_feedback,
            output_console=console,
        )

    def _display_supportive_feedback(self, response: AIMessage) -> None:
        """Render wrong-answer feedback without making the user feel punished."""
        return cli_display.display_supportive_feedback(response, output_console=console)

    def _hint_level_label(self, hint_level: int) -> str:
        """Return a human-readable label for progressive hint levels."""
        return cli_display.hint_level_label(hint_level)

    def _show_analysis_result(self, topic_state: TopicState) -> None:
        """Display the result of material analysis."""
        return cli_display.show_analysis_result(topic_state, output_console=console)

    def _show_append_result(
        self,
        new_chunks: list[ChunkState],
        previous_total: int,
        source_label: str,
    ) -> None:
        """Display appended chunks and make it clear the current question continues."""
        return cli_display.show_append_result(
            new_chunks,
            previous_total,
            source_label,
            output_console=console,
        )

    def _show_progress(self) -> None:
        """Display current learning progress."""
        return cli_display.show_progress(self.current_engine, output_console=console)

    def _format_chunk_status(self, chunk: ChunkState) -> str:
        """Return a human-readable learning status."""
        return cli_display.format_chunk_status(chunk)

    def _show_chunk_list(self) -> None:
        """Display all chunks in the current topic."""
        return cli_display.show_chunk_list(self.current_engine, output_console=console)

    def _show_review_items(self) -> None:
        """Display chunks that need review."""
        return cli_display.show_review_items(self.current_engine, output_console=console)

    def _show_history_topics(self) -> None:
        """Display archived learning topics from the user profile."""
        return cli_display.show_history_topics(
            self._load_or_create_profile(),
            output_console=console,
        )

    def _format_optional_time(self, value: datetime | None) -> str:
        """Format an optional datetime for compact tables."""
        return cli_display.format_optional_time(value)

    def _match_review_topic(self, user_input: str) -> LearnedTopic | None:
        """Match a natural-language review request to an archived topic."""
        profile = self._load_or_create_profile()
        matched = match_history_topic(user_input, profile.history_topics)
        return matched if isinstance(matched, LearnedTopic) else None

    def _show_help(self) -> None:
        """Display available commands."""
        return cli_display.show_help(output_console=console)

    def _show_summary(self, topic_state: TopicState) -> None:
        """Display a learning summary at the end of a topic."""
        mastered, needs_review, total = cli_display.show_summary(
            topic_state,
            output_console=console,
        )
        self._archive_completed_topic(topic_state, mastered, needs_review, total)
        self._save_progress()

    def _show_review_summary(
        self,
        topic_state: TopicState,
        review_stats: dict[str, int],
    ) -> None:
        """Display a review-session summary report."""
        return cli_display.show_review_summary(
            topic_state,
            review_stats,
            self._remaining_review_items(topic_state),
            output_console=console,
        )

    def _remaining_review_items(
        self,
        topic_state: TopicState,
    ) -> list[tuple[int, ChunkState]]:
        """Return chunks that still need attention after a review session."""
        return cli_review.remaining_review_items(self, topic_state)

    def _chunk_still_needs_review(self, chunk: ChunkState) -> bool:
        """Decide whether a chunk remains weak after the current review."""
        return cli_review.chunk_still_needs_review(chunk)

    def _record_review_completion(self, topic_state: TopicState) -> None:
        """Update history metadata after a review session finishes."""
        cli_review.record_review_completion(
            self,
            topic_state,
            learned_topic_cls=LearnedTopic,
        )
        console.print("[dim]已更新历史记录的复习时间和待巩固数量。[/dim]")

    def _load_or_create_profile(self) -> UserProfile:
        """Load the current user profile, filling defaults for older profiles."""
        profile_data = self.storage.load_user_profile() or {}
        profile_data = {"user_id": self.user_id, "level": self.user_level, **profile_data}
        return UserProfile.model_validate(profile_data)

    def _archive_completed_topic(
        self,
        topic_state: TopicState,
        mastered: int,
        needs_review: int,
        total: int,
    ) -> None:
        """Archive a completed topic into the user profile for future review."""
        profile = self._load_or_create_profile()
        learned_topic = LearnedTopic(
            topic_id=topic_state.topic_id,
            title=topic_state.title or topic_state.topic_id,
            summary=topic_state.summary,
            completed_at=datetime.now(),
            total_chunks=total,
            mastered_chunks=mastered,
            review_chunks=needs_review,
            source_type=topic_state.source_type,
            source_path=topic_state.source_path,
        )

        profile.history_topics = [
            topic
            for topic in profile.history_topics
            if topic.topic_id != topic_state.topic_id
        ]
        profile.history_topics.insert(0, learned_topic)
        profile.total_topics = len(profile.history_topics)
        profile.completed_topics = len(profile.history_topics)
        profile.updated_at = datetime.now()
        self.storage.save_user_profile(profile.model_dump(mode="json"))
        console.print("[dim]已归档到历史学习记录，可用 /history 查看。[/dim]")

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
    parser = argparse.ArgumentParser(
        description="🎓 Teacher-skill 数字助教",
        epilog="推荐用法: python main.py --demo 或 python main.py --file article.md",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--file",
        help="从文件加载学习材料（支持 .md/.txt/.pdf）",
        default=None,
    )
    input_group.add_argument(
        "--demo",
        action="store_true",
        help="使用内置示例材料体验完整学习闭环",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="检查 API Key、配置文件、依赖和示例材料是否准备好",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="首次配置向导：选择模型服务商、粘贴 API Key、自动写入 .env/config.yaml",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="已合并到 --setup，请使用 --setup 或直接运行 main.py",
    )
    args = parser.parse_args()

    # --init 是 --setup 的别名，保持向后兼容
    if args.setup or args.init:
        if not run_setup_wizard():
            sys.exit(1)
        return

    if args.check:
        if not run_environment_check():
            sys.exit(1)
        return

    try:
        load_runtime_dependencies()
    except ModuleNotFoundError as exc:
        console.print(f"[red]缺少运行依赖：{exc.name}[/red]")
        console.print("[yellow]请先运行：python -m pip install -r requirements.txt[/yellow]")
        console.print("[dim]也可以运行 python main.py --check 查看完整检查结果。[/dim]")
        sys.exit(1)

    # ─── Auto-detect missing config and guide into setup ───
    checks, is_ready = collect_environment_checks(project_root=PROJECT_ROOT)

    if not is_ready:
        failed_required = [
            c for c in checks if not c["passed"] and c["required"]
        ]
        failed_names = [c["name"] for c in failed_required]
        console.print(
            f"\n[yellow]⚠️ 检测到以下配置项尚未就绪：{', '.join(failed_names)}[/yellow]"
        )
        console.print(
            "[dim]你可以随时运行：python main.py --setup 进行完整配置[/dim]\n"
        )

        choice = console.input(
            "[bold cyan]是否现在运行配置向导？（Y/n）：[/bold cyan] "
        ).strip().lower()

        if choice not in ("n", "no"):
            if run_setup_wizard():
                # Re-check after successful setup
                checks, is_ready = collect_environment_checks(
                    project_root=PROJECT_ROOT
                )
            else:
                console.print("[red]配置未完成，无法启动。[/red]")
                sys.exit(1)

        if not is_ready:
            console.print("[red]环境检查未通过，无法启动。[/red]")
            console.print("[dim]运行 python main.py --setup 完成配置后再试。[/dim]")
            sys.exit(1)

    app = TeacherSkillApp()
    app.run(file_path=args.file, demo=args.demo)


if __name__ == "__main__":
    main()
