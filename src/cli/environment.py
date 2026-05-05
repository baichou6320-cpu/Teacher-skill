"""Startup initialization and environment checks for the CLI."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Mapping


def collect_environment_checks(
    env: Mapping[str, str] | None = None,
    project_root: Path | None = None,
) -> tuple[list[dict[str, object]], bool]:
    """Collect startup checks without entering the learning flow."""
    env = env or os.environ
    project_root = project_root or Path.cwd()
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
        api_key = read_env_file_value(env_file, "ANTHROPIC_API_KEY")
    add(
        "ANTHROPIC_API_KEY",
        bool(api_key and api_key != "your_api_key_here"),
        "已配置" if api_key and api_key != "your_api_key_here" else "未配置或仍是占位值",
    )

    config_info = inspect_config_file(project_root)
    add(
        "config.yaml",
        bool(config_info["passed"]),
        str(config_info["detail"]),
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


def read_env_file_value(env_file: Path, key: str) -> str:
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
    project_root = project_root or Path.cwd()
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

    sections = read_simple_yaml_sections(config_path)
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
    project_root = project_root or Path.cwd()
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

    data_dir, logs_dir = read_runtime_dirs_from_config(project_root)
    for label, directory in (("数据目录", data_dir), ("日志目录", logs_dir)):
        directory.mkdir(parents=True, exist_ok=True)
        add(label, "已准备", format_project_path(project_root, directory))

    sample_path = project_root / "samples" / "demo_article.md"
    add(
        "Demo 示例材料",
        "可用" if sample_path.exists() else "缺失",
        format_project_path(project_root, sample_path)
        if sample_path.exists()
        else "缺少 samples/demo_article.md",
    )

    is_ok = all(action["status"] != "失败" for action in actions)
    return actions, is_ok


def read_runtime_dirs_from_config(project_root: Path) -> tuple[Path, Path]:
    """Read data/log dirs from config.yaml with a tiny stdlib parser."""
    config_path = project_root / "config.yaml"
    sections = read_simple_yaml_sections(config_path)
    data_dir = sections.get("paths", {}).get("data_dir", "./data")
    logs_dir = sections.get("paths", {}).get("logs_dir", "./logs")

    return resolve_project_path(project_root, data_dir), resolve_project_path(project_root, logs_dir)


def read_simple_yaml_sections(config_path: Path) -> dict[str, dict[str, str]]:
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


def resolve_project_path(project_root: Path, value: str) -> Path:
    """Resolve config paths relative to the project root."""
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def format_project_path(project_root: Path, path: Path) -> str:
    """Format paths relative to the project root when possible."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def render_project_init(project_root: Path, *, output_console, table_cls, panel_cls) -> bool:
    """Render first-run initialization actions."""
    actions, is_ok = initialize_project(project_root)
    table = table_cls(title="项目初始化")
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

    output_console.print(table)
    if is_ok:
        output_console.print(
            panel_cls.fit(
                "[bold green]初始化完成。[/bold green]\n\n"
                "下一步：\n"
                "1. 打开 `.env`，填写 `ANTHROPIC_API_KEY`\n"
                "2. 运行 `python main.py --check`\n"
                "3. 运行 `python main.py --demo`",
                border_style="green",
            )
        )
    else:
        output_console.print(
            panel_cls.fit(
                "[bold yellow]初始化没有完全成功。[/bold yellow]\n\n"
                "请先处理失败项，然后再次运行 `python main.py --init`。",
                border_style="yellow",
            )
        )
    return is_ok


def render_environment_check(
    project_root: Path,
    *,
    output_console,
    table_cls,
    panel_cls,
) -> bool:
    """Render environment checks and return whether the app can start."""
    checks, is_ready = collect_environment_checks(project_root=project_root)
    table = table_cls(title="启动环境检查")
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

    output_console.print(table)
    if is_ready:
        output_console.print(
            panel_cls.fit(
                "[bold green]环境可以启动 Teacher-skill。[/bold green]\n\n"
                "下一步可以运行：\n"
                "[green]python main.py --demo[/green]\n"
                "或：\n"
                "[green]python main.py --file article.md[/green]",
                border_style="green",
            )
        )
    else:
        output_console.print(
            panel_cls.fit(
                "[bold yellow]环境还没准备好。[/bold yellow]\n\n"
                "优先处理红色项目；常见修复：\n"
                "1. 复制 `.env.example` 为 `.env`\n"
                "2. 填写 `ANTHROPIC_API_KEY`\n"
                "3. 运行 `pip install -r requirements.txt`",
                border_style="yellow",
            )
        )
    return is_ready

