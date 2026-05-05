"""Teacher-skill 唯一入口 — 控制 CLI 交互与初始化。"""
from __future__ import annotations

import argparse
import builtins
import importlib.util
import os
import re
import shutil
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
from typing import Mapping

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs) -> bool:
        """Fallback when python-dotenv is not installed yet."""
        return False

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
        """Small console fallback so `--check` can run before rich is installed."""

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

load_dotenv()

console = Console()
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
    env = env or os.environ
    project_root = project_root or PROJECT_ROOT
    checks: list[dict[str, object]] = []

    def add(
        name: str,
        passed: bool,
        detail: str,
        *,
        required: bool = True,
    ) -> None:
        checks.append(
            {
                "name": name,
                "passed": passed,
                "required": required,
                "detail": detail,
            }
        )

    add(
        "Python 版本",
        sys.version_info >= (3, 10),
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}；需要 3.10+",
    )

    env_file = project_root / ".env"
    add(
        ".env 文件",
        env_file.exists(),
        ".env 存在" if env_file.exists() else "未找到 .env；可从 .env.example 复制一份",
        required=False,
    )

    api_key = (env.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key and env_file.exists():
        api_key = _read_env_file_value(env_file, "ANTHROPIC_API_KEY")
    add(
        "ANTHROPIC_API_KEY",
        bool(api_key and api_key != "your_api_key_here"),
        "已配置" if api_key and api_key != "your_api_key_here" else "未配置或仍是占位值",
    )

    config_info = inspect_config_file(project_root)
    add(
        "config.yaml",
        config_info["passed"],
        config_info["detail"],
    )
    add(
        "数据目录配置",
        bool(config_info["data_dir"] and config_info["logs_dir"]),
        f"data_dir={config_info['data_dir']}；logs_dir={config_info['logs_dir']}",
    )

    demo_path = project_root / "samples" / "demo_article.md"
    add(
        "Demo 示例材料",
        demo_path.exists(),
        str(demo_path.relative_to(project_root)) if demo_path.exists() else "缺少 samples/demo_article.md",
    )

    runtime_modules = {
        "anthropic": "anthropic",
        "pydantic": "pydantic",
        "python-dotenv": "dotenv",
        "pypdf": "pypdf",
        "rich": "rich",
        "PyYAML": "yaml",
    }
    missing_runtime = [
        package
        for package, module_name in runtime_modules.items()
        if importlib.util.find_spec(module_name) is None
    ]
    add(
        "运行依赖",
        not missing_runtime,
        "已安装" if not missing_runtime else "缺少：" + ", ".join(missing_runtime),
    )

    test_modules = {
        "pytest": "pytest",
        "pytest-mock": "pytest_mock",
        "freezegun": "freezegun",
    }
    missing_test = [
        package
        for package, module_name in test_modules.items()
        if importlib.util.find_spec(module_name) is None
    ]
    add(
        "测试依赖",
        not missing_test,
        "已安装" if not missing_test else "缺少：" + ", ".join(missing_test),
        required=False,
    )

    is_ready = all(
        bool(check["passed"])
        for check in checks
        if bool(check["required"])
    )
    return checks, is_ready


def _read_env_file_value(env_file: Path, key: str) -> str:
    """Read one simple KEY=value entry from .env without python-dotenv."""
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def inspect_config_file(project_root: Path | None = None) -> dict[str, object]:
    """Inspect config.yaml, falling back to a stdlib parser if deps are missing."""
    project_root = project_root or PROJECT_ROOT
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        return {
            "passed": False,
            "detail": "缺少 config.yaml",
            "data_dir": "",
            "logs_dir": "",
        }

    can_use_full_parser = (
        importlib.util.find_spec("yaml") is not None
        and importlib.util.find_spec("pydantic") is not None
    )
    if can_use_full_parser:
        try:
            import yaml
            from src.utils.config import Config

            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}
            cfg = Config(**raw_config)
            return {
                "passed": bool(cfg.llm.model_id),
                "detail": f"模型：{cfg.llm.model_id}；prompt_mode={cfg.teaching.prompt_mode}",
                "data_dir": cfg.paths.data_dir,
                "logs_dir": cfg.paths.logs_dir,
            }
        except Exception as exc:
            return {
                "passed": False,
                "detail": f"读取失败：{exc}",
                "data_dir": "",
                "logs_dir": "",
            }

    sections = _read_simple_yaml_sections(config_path)
    model_id = sections.get("llm", {}).get("model_id", "claude-sonnet-4-20250514")
    prompt_mode = sections.get("teaching", {}).get("prompt_mode", "split")
    data_dir = sections.get("paths", {}).get("data_dir", "./data")
    logs_dir = sections.get("paths", {}).get("logs_dir", "./logs")
    return {
        "passed": bool(model_id),
        "detail": f"模型：{model_id}；prompt_mode={prompt_mode}（轻量解析）",
        "data_dir": data_dir,
        "logs_dir": logs_dir,
    }


def initialize_project(
    project_root: Path | None = None,
) -> tuple[list[dict[str, str]], bool]:
    """Prepare first-run local files without requiring runtime dependencies."""
    project_root = project_root or PROJECT_ROOT
    actions: list[dict[str, str]] = []

    def add(item: str, status: str, detail: str) -> None:
        actions.append({"item": item, "status": status, "detail": detail})

    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    if env_file.exists():
        add(".env", "已存在", "保留现有 .env，不覆盖")
    elif env_example.exists():
        shutil.copyfile(env_example, env_file)
        add(".env", "已创建", "已从 .env.example 复制；请填写 ANTHROPIC_API_KEY")
    else:
        add(".env", "失败", "缺少 .env.example，无法自动创建")

    data_dir, logs_dir = _read_runtime_dirs_from_config(project_root)
    for label, directory in (("数据目录", data_dir), ("日志目录", logs_dir)):
        directory.mkdir(parents=True, exist_ok=True)
        add(label, "已准备", _format_project_path(project_root, directory))

    sample_path = project_root / "samples" / "demo_article.md"
    add(
        "Demo 示例材料",
        "可用" if sample_path.exists() else "缺失",
        _format_project_path(project_root, sample_path)
        if sample_path.exists()
        else "缺少 samples/demo_article.md",
    )

    is_ok = all(action["status"] != "失败" for action in actions)
    return actions, is_ok


def _read_runtime_dirs_from_config(project_root: Path) -> tuple[Path, Path]:
    """Read data/log dirs from config.yaml with a tiny stdlib parser."""
    config_path = project_root / "config.yaml"
    sections = _read_simple_yaml_sections(config_path)
    data_dir = sections.get("paths", {}).get("data_dir", "./data")
    logs_dir = sections.get("paths", {}).get("logs_dir", "./logs")

    return _resolve_project_path(project_root, data_dir), _resolve_project_path(project_root, logs_dir)


def _read_simple_yaml_sections(config_path: Path) -> dict[str, dict[str, str]]:
    """Read simple top-level YAML sections containing scalar key/value pairs."""
    sections: dict[str, dict[str, str]] = {}
    current_section: str | None = None

    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return sections

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line and not line.startswith((" ", "\t")):
            current_section = stripped[:-1].strip() if stripped.endswith(":") else None
            if current_section:
                sections.setdefault(current_section, {})
            continue
        if not current_section or ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        if value:
            sections[current_section][key.strip()] = value

    return sections


def _resolve_project_path(project_root: Path, value: str) -> Path:
    """Resolve config paths relative to the project root."""
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def _format_project_path(project_root: Path, path: Path) -> str:
    """Format paths relative to the project root when possible."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def run_project_init() -> bool:
    """Render first-run initialization actions."""
    actions, is_ok = initialize_project()
    table = Table(title="项目初始化")
    table.add_column("项目", style="cyan")
    table.add_column("状态", width=10)
    table.add_column("说明", style="white")

    for action in actions:
        status = action["status"]
        if status in ("已创建", "已准备", "可用"):
            rendered_status = "[green]" + status + "[/green]"
        elif status == "已存在":
            rendered_status = "[yellow]" + status + "[/yellow]"
        else:
            rendered_status = "[red]" + status + "[/red]"
        table.add_row(action["item"], rendered_status, action["detail"])

    console.print(table)
    if is_ok:
        console.print(
            Panel.fit(
                "[bold green]初始化完成。[/bold green]\n\n"
                "下一步：\n"
                "1. 打开 `.env`，填写 `ANTHROPIC_API_KEY`\n"
                "2. 运行 `python main.py --check`\n"
                "3. 运行 `python main.py --demo`",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[bold yellow]初始化没有完全成功。[/bold yellow]\n\n"
                "请先处理失败项，然后再次运行 `python main.py --init`。",
                border_style="yellow",
            )
        )
    return is_ok


def run_environment_check() -> bool:
    """Render environment checks and return whether the app can start."""
    checks, is_ready = collect_environment_checks()
    table = Table(title="启动环境检查")
    table.add_column("项目", style="cyan")
    table.add_column("结果", width=10)
    table.add_column("说明", style="white")

    for check in checks:
        passed = bool(check["passed"])
        required = bool(check["required"])
        if passed:
            result = "[green]通过[/green]"
        elif required:
            result = "[red]需处理[/red]"
        else:
            result = "[yellow]建议[/yellow]"
        table.add_row(str(check["name"]), result, str(check["detail"]))

    console.print(table)
    if is_ready:
        console.print(
            Panel.fit(
                "[bold green]环境可以启动 Teacher-skill。[/bold green]\n\n"
                "下一步可以运行：\n"
                "[green]python main.py --demo[/green]\n"
                "或：\n"
                "[green]python main.py --file article.md[/green]",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[bold yellow]环境还没准备好。[/bold yellow]\n\n"
                "优先处理红色项目；常见修复：\n"
                "1. 复制 `.env.example` 为 `.env`\n"
                "2. 填写 `ANTHROPIC_API_KEY`\n"
                "3. 运行 `pip install -r requirements.txt`",
                border_style="yellow",
            )
        )
    return is_ready


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
            choice = console.input("\n[bold blue>[/bold blue] ").strip()
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

    def _topic_display_summary(self, state: dict) -> str:
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

    def _topic_source_label(self, state: dict) -> str:
        """Return a readable material source label."""
        source_type = str(state.get("source_type") or "").strip()
        source_path = str(state.get("source_path") or "").strip()
        if source_type == "demo":
            return "内置示例"
        if source_path:
            return f"文件 {Path(source_path).name}"
        if source_type == "file":
            return "文件"
        return "手动输入"

    def _format_topic_time(self, state: dict) -> str:
        """Format topic timestamp for display."""
        value = state.get("updated_at") or state.get("created_at")
        if not value:
            return ""
        try:
            return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return str(value)

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
        self.logger.info(f"Reviewing topic {topic_id}")
        console.print(f"\n[cyan]正在进入复习模式：{topic_id}...[/cyan]")
        state_data = self.storage.load_topic_state(topic_id)
        history_data = self.storage.load_conversation_history(topic_id)

        if not state_data:
            self.logger.error(f"Failed to load topic state for review: {topic_id}")
            console.print("[red]无法加载该主题的学习进度[/red]")
            return

        topic_state = TopicState.model_validate(state_data)
        self.current_engine = TutorEngine(self.user_id, topic_id)
        if history_data and history_data.get("messages"):
            self.current_engine.restore_memory(history_data["messages"])

        console.print(
            Panel.fit(
                f"[bold cyan]复习模式：{escape(topic_state.title or topic_id)}[/bold cyan]\n\n"
                "本轮会优先提问待巩固、答错过或用过提示的知识点。\n"
                "[dim]复习模式会直接提问，不重新讲解；可用 /direct 查看答案，/skip 跳过。[/dim]",
                border_style="cyan",
            )
        )
        response = self.current_engine.start_review(topic_state)
        self._display_response(response)
        if response.is_final:
            self._finish_review_session(topic_state, self._new_review_stats())
            return

        self._review_loop(topic_state)
        self._save_progress()

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
            user_input = console.input("[bold blue材料>[/bold blue] ").strip()
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
        self.logger.info(f"Review loop started: {topic_state.total_chunks} chunks")
        review_stats = self._new_review_stats()

        while True:
            user_input = console.input("\n[bold blue复习>[/bold blue] ").strip()
            if not user_input:
                continue

            lowered = user_input.lower()
            if lowered in ("/help", "help"):
                self._show_help()
                continue

            if lowered in ("/exit", "/quit", "exit", "quit"):
                self.logger.info("User requested exit from review, saving progress")
                self._save_progress()
                console.print("[cyan]已保存复习进度，下次再见！[/cyan]")
                sys.exit(0)

            if lowered == "/direct":
                response = self.current_engine.receive_answer("", is_direct=True)
                self._record_review_result(review_stats, response, is_direct=True)
                self._display_response(response)
                if self._advance_review_or_finish():
                    self._finish_review_session(topic_state, review_stats)
                    break
                continue

            if lowered == "/progress":
                self._show_progress()
                continue

            if lowered == "/list":
                self._show_chunk_list()
                continue

            if lowered == "/review":
                self._show_review_items()
                continue

            if lowered == "/history":
                self._show_history_topics()
                continue

            if lowered == "/skip":
                response = self.current_engine.skip_review_chunk()
                self._record_review_result(review_stats, response, is_skipped=True)
                self._display_response(response)
                self._save_progress()
                if response.is_final:
                    self._finish_review_session(topic_state, review_stats)
                    break
                continue

            if self._parse_load_command(user_input) is not None:
                console.print("[yellow]复习模式暂不追加材料；请退出后用 /load 或 --file 学习新材料。[/yellow]")
                continue

            confirmed_answer = self._confirm_answer_submission(user_input)
            if confirmed_answer is None:
                continue

            self.logger.debug(f"Review answer: {confirmed_answer[:50]}...")
            response = self.current_engine.receive_answer(confirmed_answer, is_direct=False)
            self._record_review_result(review_stats, response)
            self._display_response(response)

            if self._review_response_finishes_item(response):
                if self._advance_review_or_finish():
                    self._finish_review_session(topic_state, review_stats)
                    break

    def _new_review_stats(self) -> dict[str, int]:
        """Create counters for one review session."""
        return {
            "answered": 0,
            "correct": 0,
            "direct": 0,
            "skipped": 0,
            "kept_review": 0,
        }

    def _record_review_result(
        self,
        stats: dict[str, int],
        response: AIMessage,
        *,
        is_direct: bool = False,
        is_skipped: bool = False,
    ) -> None:
        """Update review-session counters from one user action."""
        if is_skipped:
            stats["skipped"] += 1
            stats["kept_review"] += 1
            return

        if is_direct:
            stats["direct"] += 1
            stats["kept_review"] += 1
            return

        stats["answered"] += 1
        if response.response_type == ResponseType.FEEDBACK_CORRECT:
            stats["correct"] += 1
            return

        if response.is_final and response.response_type in (
            ResponseType.FEEDBACK_WRONG,
            ResponseType.FEEDBACK_HINT,
        ):
            stats["kept_review"] += 1

    def _review_response_finishes_item(self, response: AIMessage) -> bool:
        """Return whether a review response should move to the next review item."""
        return response.response_type in (
            ResponseType.FEEDBACK_CORRECT,
            ResponseType.DIRECT_ANSWER,
        ) or (
            response.is_final
            and response.response_type
            in (ResponseType.FEEDBACK_WRONG, ResponseType.FEEDBACK_HINT)
        )

    def _advance_review_or_finish(self) -> bool:
        """Move to the next review item.

        Returns True when the review queue is complete.
        """
        response = self.current_engine.next_review_chunk()
        self._display_response(response)
        return response.is_final

    def _finish_review_session(
        self,
        topic_state: TopicState,
        review_stats: dict[str, int],
    ) -> None:
        """Show review summary and persist review metadata."""
        self._show_review_summary(topic_state, review_stats)
        self._record_review_completion(topic_state)
        self._save_progress()

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
            choice = console.input("[bold blue确认>[/bold blue] ").strip()
            if not choice:
                return current_answer

            lowered = choice.lower()
            if lowered == "/cancel":
                console.print("[cyan]已取消本次回答，可以重新输入。[/cyan]")
                return None

            if lowered == "/edit":
                edited = console.input("[bold blue修改回答>[/bold blue] ").strip()
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
                self._display_supportive_feedback(response)
            case ResponseType.DIRECT_ANSWER:
                console.print(
                    Panel.fit(
                        f"[bold yellow]【速查模式】[/bold yellow]\n\n{response.content}",
                        border_style="yellow",
                    )
                )

    def _display_supportive_feedback(self, response: AIMessage) -> None:
        """Render wrong-answer feedback without making the user feel punished."""
        hint_level = max(0, min(response.hint_level, 4))
        title = "还差一点，我们换个角度试试"
        if hint_level >= 4:
            title = "这一题先放进待巩固，我们保留节奏继续前进"

        details = []
        if hint_level > 0:
            details.append(
                f"提示层级：第 {hint_level}/4 层（{self._hint_level_label(hint_level)}）"
            )
        details.append("你可以继续尝试；想先看答案可输入 /direct，系统会标记为待巩固。")

        console.print(
            Panel.fit(
                f"[bold yellow]{title}[/bold yellow]\n\n"
                f"{escape(response.content)}\n\n"
                f"[dim]{escape(' · '.join(details))}[/dim]",
                border_style="yellow",
            )
        )

    def _hint_level_label(self, hint_level: int) -> str:
        """Return a human-readable label for progressive hint levels."""
        labels = {
            1: "线索提示",
            2: "生活类比",
            3: "半解析",
            4: "关键词/部分答案",
        }
        return labels.get(hint_level, "渐进提示")

    def _show_analysis_result(self, topic_state: TopicState) -> None:
        """Display the result of material analysis."""
        console.print(
            Panel.fit(
                f"[bold green]✅ 材料分析完成！[/bold green]\n\n"
                f"主题：{escape(topic_state.title or topic_state.topic_id)}\n"
                f"摘要：{escape(topic_state.summary or '暂无')}\n"
                f"来源：{escape(self._topic_source_label(topic_state.model_dump(mode='json')))}\n"
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

    def _show_append_result(
        self,
        new_chunks: list[ChunkState],
        previous_total: int,
        source_label: str,
    ) -> None:
        """Display appended chunks and make it clear the current question continues."""
        console.print(
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
            table.add_row(str(i), chunk.title or "未命名", chunk.difficulty)

        console.print(table)
        console.print()

    def _show_progress(self) -> None:
        """Display current learning progress."""
        if not self.current_engine or not self.current_engine.topic_state:
            return

        ts = self.current_engine.topic_state
        mastered = sum(1 for c in ts.chunks if c.status == LearningStatus.MASTERED)
        needs_review = sum(1 for c in ts.chunks if c.status == LearningStatus.NEEDS_REVIEW)
        not_started = sum(1 for c in ts.chunks if c.status == LearningStatus.NOT_STARTED)
        attempts = sum(c.attempts for c in ts.chunks)
        wrong = sum(c.fail_count for c in ts.chunks)
        current = ts.chunks[ts.current_chunk_index] if ts.chunks and ts.current_chunk_index < len(ts.chunks) else None
        review_progress = (
            self.current_engine.get_review_progress()
            if hasattr(self.current_engine, "get_review_progress")
            else "未开始"
        )
        review_line = (
            f"\n复习进度: [cyan]{review_progress}[/cyan]"
            if review_progress != "未开始"
            else ""
        )
        console.print(
            Panel.fit(
                f"[bold]当前进度[/bold]\n\n"
                f"知识点: {ts.current_chunk_index + 1}/{ts.total_chunks}\n"
                f"当前: {current.title if current else '无'}\n"
                f"已掌握: [green]{mastered}[/green]\n"
                f"待巩固: [yellow]{needs_review}[/yellow]\n"
                f"未开始: {not_started}\n"
                f"本主题作答: {attempts} 次，答错: {wrong} 次\n"
                f"状态: {ts.is_completed and '已完成' or '进行中'}"
                f"{review_line}",
                border_style="cyan",
            )
        )

    def _format_chunk_status(self, chunk: ChunkState) -> str:
        """Return a human-readable learning status."""
        status_map = {
            LearningStatus.NOT_STARTED: "未开始",
            LearningStatus.IN_PROGRESS: "学习中",
            LearningStatus.MASTERED: "已掌握",
            LearningStatus.NEEDS_REVIEW: "待巩固",
        }
        return status_map.get(chunk.status, str(chunk.status))

    def _show_chunk_list(self) -> None:
        """Display all chunks in the current topic."""
        if not self.current_engine or not self.current_engine.topic_state:
            console.print("[yellow]当前没有进行中的学习主题[/yellow]")
            return

        ts = self.current_engine.topic_state
        table = Table(title="📚 知识点列表")
        table.add_column("当前", width=4)
        table.add_column("序号", style="cyan", width=4)
        table.add_column("标题", style="white")
        table.add_column("状态", style="yellow", width=8)
        table.add_column("答错", width=6)
        table.add_column("提示", width=6)

        for i, chunk in enumerate(ts.chunks, 1):
            table.add_row(
                "→" if i - 1 == ts.current_chunk_index else "",
                str(i),
                chunk.title or "未命名",
                self._format_chunk_status(chunk),
                str(chunk.fail_count),
                str(chunk.hint_level),
            )

        console.print(table)
        console.print("[dim]可用 /jump <序号> 跳转到指定知识点。[/dim]")

    def _show_review_items(self) -> None:
        """Display chunks that need review."""
        if not self.current_engine or not self.current_engine.topic_state:
            console.print("[yellow]当前没有进行中的学习主题[/yellow]")
            return

        ts = self.current_engine.topic_state
        review_items = [
            (i, chunk)
            for i, chunk in enumerate(ts.chunks, 1)
            if chunk.status == LearningStatus.NEEDS_REVIEW
            or chunk.fail_count > 0
            or chunk.hint_level > 0
        ]

        if not review_items:
            console.print("[green]当前没有待巩固知识点。[/green]")
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
                chunk.title or "未命名",
                self._format_chunk_status(chunk),
                str(chunk.fail_count),
                str(chunk.hint_level),
            )

        console.print(table)
        console.print("[dim]可用 /jump <序号> 回到对应知识点。[/dim]")

    def _show_history_topics(self) -> None:
        """Display archived learning topics from the user profile."""
        profile = self._load_or_create_profile()
        if not profile.history_topics:
            console.print("[yellow]还没有历史学习记录。完成一个主题后会自动归档到这里。[/yellow]")
            return

        table = Table(title="📚 历史学习记录")
        table.add_column("序号", style="cyan", width=4)
        table.add_column("主题", style="white")
        table.add_column("掌握", style="green", width=8)
        table.add_column("待巩固", style="yellow", width=8)
        table.add_column("完成时间", style="dim", width=16)
        table.add_column("上次复习", style="dim", width=16)

        for i, topic in enumerate(profile.history_topics, 1):
            table.add_row(
                str(i),
                escape(topic.title or topic.topic_id),
                f"{topic.mastered_chunks}/{topic.total_chunks}",
                str(topic.review_chunks),
                topic.completed_at.strftime("%Y-%m-%d %H:%M"),
                self._format_optional_time(topic.last_reviewed_at),
            )

        console.print(table)
        console.print("[dim]后续复习模式会优先使用这些历史记录和待巩固知识点。[/dim]")

    def _format_optional_time(self, value: datetime | None) -> str:
        """Format an optional datetime for compact tables."""
        if not value:
            return "未复习"
        return value.strftime("%Y-%m-%d %H:%M")

    def _match_review_topic(self, user_input: str) -> LearnedTopic | None:
        """Match a natural-language review request to an archived topic."""
        profile = self._load_or_create_profile()
        matched = match_history_topic(user_input, profile.history_topics)
        return matched if isinstance(matched, LearnedTopic) else None

    def _show_help(self) -> None:
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
                f"主题: [cyan]{escape(topic_state.title or topic_state.topic_id)}[/cyan]\n"
                f"掌握: [green]{mastered}[/green] / {total}\n"
                f"待巩固: [yellow]{needs_review}[/yellow]\n"
                f"完成率: [cyan]{rate:.0f}%[/cyan]",
                border_style="green",
            )
        )
        self._archive_completed_topic(topic_state, mastered, needs_review, total)
        self._save_progress()

    def _show_review_summary(
        self,
        topic_state: TopicState,
        review_stats: dict[str, int],
    ) -> None:
        """Display a review-session summary report."""
        total = len(topic_state.chunks)
        mastered = sum(1 for c in topic_state.chunks if c.status == LearningStatus.MASTERED)
        remaining_review = self._remaining_review_items(topic_state)
        correct_rate = (
            review_stats["correct"] / review_stats["answered"] * 100
            if review_stats["answered"]
            else 0
        )

        console.print(
            Panel.fit(
                f"[bold green]✅ 本轮复习完成[/bold green]\n\n"
                f"主题: [cyan]{escape(topic_state.title or topic_state.topic_id)}[/cyan]\n"
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
            console.print("[green]这轮复习后没有仍需巩固的知识点。[/green]")
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
                escape(chunk.title or "未命名"),
                self._format_chunk_status(chunk),
                str(chunk.fail_count),
                str(chunk.hint_level),
            )

        console.print(table)
        if len(remaining_review) > 8:
            console.print(f"[dim]还有 {len(remaining_review) - 8} 个待巩固知识点未显示。[/dim]")

    def _remaining_review_items(
        self,
        topic_state: TopicState,
    ) -> list[tuple[int, ChunkState]]:
        """Return chunks that still need attention after a review session."""
        return [
            (i, chunk)
            for i, chunk in enumerate(topic_state.chunks, 1)
            if self._chunk_still_needs_review(chunk)
        ]

    def _chunk_still_needs_review(self, chunk: ChunkState) -> bool:
        """Decide whether a chunk remains weak after the current review."""
        if chunk.status == LearningStatus.NEEDS_REVIEW:
            return True
        return chunk.status != LearningStatus.MASTERED and (
            chunk.fail_count > 0 or chunk.hint_level > 0
        )

    def _record_review_completion(self, topic_state: TopicState) -> None:
        """Update history metadata after a review session finishes."""
        profile = self._load_or_create_profile()
        now = datetime.now()
        total = len(topic_state.chunks)
        mastered = sum(1 for c in topic_state.chunks if c.status == LearningStatus.MASTERED)
        needs_review = len(self._remaining_review_items(topic_state))

        for topic in profile.history_topics:
            if topic.topic_id == topic_state.topic_id:
                topic.title = topic_state.title or topic.title or topic.topic_id
                topic.summary = topic_state.summary or topic.summary
                topic.total_chunks = total
                topic.mastered_chunks = mastered
                topic.review_chunks = needs_review
                topic.source_type = topic_state.source_type
                topic.source_path = topic_state.source_path
                topic.last_reviewed_at = now
                break
        else:
            profile.history_topics.insert(
                0,
                LearnedTopic(
                    topic_id=topic_state.topic_id,
                    title=topic_state.title or topic_state.topic_id,
                    summary=topic_state.summary,
                    completed_at=topic_state.created_at,
                    total_chunks=total,
                    mastered_chunks=mastered,
                    review_chunks=needs_review,
                    source_type=topic_state.source_type,
                    source_path=topic_state.source_path,
                    last_reviewed_at=now,
                ),
            )

        profile.total_topics = len(profile.history_topics)
        profile.completed_topics = len(profile.history_topics)
        profile.updated_at = now
        self.storage.save_user_profile(profile.model_dump(mode="json"))
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
        "--init",
        action="store_true",
        help="初始化 .env、数据目录和日志目录，不覆盖已有配置",
    )
    args = parser.parse_args()

    if args.init:
        if not run_project_init():
            sys.exit(1)
        if not args.check:
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

    app = TeacherSkillApp()
    app.run(file_path=args.file, demo=args.demo)


if __name__ == "__main__":
    main()
