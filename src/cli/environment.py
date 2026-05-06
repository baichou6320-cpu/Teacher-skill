"""Startup initialization and environment checks for the CLI."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Mapping


MODEL_PRESETS: tuple[dict[str, str], ...] = (
    {
        "choice": "1",
        "provider": "anthropic",
        "label": "Claude / Anthropic",
        "api_format": "anthropic",
        "model_id": "claude-sonnet-4-20250514",
        "base_url": "",
        "key_url": "https://console.anthropic.com/",
    },
    {
        "choice": "2",
        "provider": "kimi",
        "label": "Kimi / Moonshot",
        "api_format": "openai",
        "model_id": "kimi-k2.5",
        "base_url": "https://api.moonshot.cn/v1",
        "key_url": "https://platform.moonshot.cn/",
    },
    {
        "choice": "3",
        "provider": "deepseek",
        "label": "DeepSeek",
        "api_format": "openai",
        "model_id": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "key_url": "https://platform.deepseek.com/",
    },
    {
        "choice": "4",
        "provider": "custom_openai",
        "label": "自定义 OpenAI 兼容接口",
        "api_format": "openai",
        "model_id": "",
        "base_url": "",
        "key_url": "",
    },
    {
        "choice": "5",
        "provider": "custom_anthropic",
        "label": "自定义 Anthropic 兼容接口",
        "api_format": "anthropic",
        "model_id": "",
        "base_url": "",
        "key_url": "",
    },
)


def collect_environment_checks(
    env: Mapping[str, str] | None = None,
    project_root: Path | None = None,
) -> tuple[list[dict[str, object]], bool]:
    """Collect startup checks without entering the learning flow."""
    if env is None:
        env = os.environ
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

    api_key = (
        env.get("TEACHER_SKILL_API_KEY")
        or env.get("ANTHROPIC_API_KEY")
        or env.get("MOONSHOT_API_KEY")
        or env.get("DEEPSEEK_API_KEY")
        or ""
    ).strip()
    if not api_key and env_file.exists():
        api_key = (
            read_env_file_value(env_file, "TEACHER_SKILL_API_KEY")
            or read_env_file_value(env_file, "ANTHROPIC_API_KEY")
            or read_env_file_value(env_file, "MOONSHOT_API_KEY")
            or read_env_file_value(env_file, "DEEPSEEK_API_KEY")
        )
    add(
        "API Key",
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
                "detail": (
                    f"服务商：{cfg.llm.provider}；模型：{cfg.llm.model_id}；"
                    f"api_format={cfg.llm.api_format}；prompt_mode={cfg.teaching.prompt_mode}"
                ),
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
    provider = sections.get("llm", {}).get("provider", "anthropic")
    api_format = sections.get("llm", {}).get("api_format", "anthropic")
    prompt_mode = sections.get("teaching", {}).get("prompt_mode", "split")
    data_dir = sections.get("paths", {}).get("data_dir", "./data")
    logs_dir = sections.get("paths", {}).get("logs_dir", "./logs")
    return {
        "passed": bool(model_id),
        "detail": (
            f"服务商：{provider}；模型：{model_id}；"
            f"api_format={api_format}；prompt_mode={prompt_mode}（轻量解析）"
        ),
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


def run_setup_wizard(
    project_root: Path | None = None,
    *,
    input_func=input,
) -> tuple[list[dict[str, str]], bool]:
    """Run a compact first-time setup wizard.

    The wizard prepares local directories, lets the user choose a model
    provider, writes ``.env`` and ``config.yaml``, then returns a concise action
    summary. It intentionally uses only the standard library so it can run
    before optional runtime dependencies are available.
    """

    project_root = project_root or Path.cwd()
    actions, _ = initialize_project(project_root)

    print("\n选择模型服务商：")
    for preset in MODEL_PRESETS:
        detail = preset["model_id"] or "需要手动填写模型名"
        print(f"  {preset['choice']}. {preset['label']} ({detail})")

    selected = _select_model_preset(input_func("请输入序号，直接回车默认 1：").strip())
    provider = dict(selected)

    if not provider["model_id"]:
        provider["model_id"] = input_func("请输入模型 ID：").strip()
    else:
        custom_model = input_func(
            f"模型默认是 {provider['model_id']}，按回车使用，或粘贴自定义模型："
        ).strip()
        if custom_model:
            provider["model_id"] = custom_model

    if not provider["base_url"] and provider["api_format"] == "openai":
        provider["base_url"] = input_func("请输入 OpenAI 兼容 base_url：").strip()
    elif provider["base_url"]:
        custom_base_url = input_func(
            f"base_url 默认是 {provider['base_url']}，按回车使用，或粘贴自定义 base_url："
        ).strip()
        if custom_base_url:
            provider["base_url"] = custom_base_url

    api_key = input_func(
        f"粘贴 {provider['label']} API Key"
        + (f"（获取地址：{provider['key_url']}）" if provider["key_url"] else "")
        + "："
    ).strip()

    if not provider["model_id"]:
        actions.append({"item": "模型", "status": "失败", "detail": "未填写模型 ID"})
        return actions, False
    if not api_key:
        actions.append({"item": "API Key", "status": "失败", "detail": "未填写 API Key"})
        return actions, False

    write_env_values(
        project_root / ".env",
        {
            "TEACHER_SKILL_API_KEY": api_key,
            "TEACHER_SKILL_BASE_URL": provider["base_url"],
            # Keep legacy variables for older scripts and existing docs.
            "ANTHROPIC_API_KEY": api_key,
            "ANTHROPIC_BASE_URL": provider["base_url"],
        },
    )
    actions.append(
        {
            "item": ".env",
            "status": "已配置",
            "detail": f"{provider['label']} API Key 已写入本地 .env",
        }
    )

    write_config_for_provider(project_root, provider)
    actions.append(
        {
            "item": "config.yaml",
            "status": "已配置",
            "detail": f"{provider['provider']} / {provider['model_id']}",
        }
    )
    return actions, True


def _select_model_preset(choice: str) -> dict[str, str]:
    """Return a model preset by user choice, defaulting to Anthropic."""

    normalized = choice or "1"
    for preset in MODEL_PRESETS:
        if preset["choice"] == normalized:
            return dict(preset)
    return dict(MODEL_PRESETS[0])


def write_env_values(env_file: Path, values: Mapping[str, str]) -> None:
    """Create or update simple KEY=value pairs in an env file."""

    existing_lines: list[str] = []
    if env_file.exists():
        existing_lines = env_file.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    output_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output_lines.append(line)
            continue
        key, _ = stripped.split("=", 1)
        key = key.strip()
        if key in values:
            output_lines.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            output_lines.append(line)

    if output_lines and output_lines[-1].strip():
        output_lines.append("")
    for key, value in values.items():
        if key not in seen:
            output_lines.append(f"{key}={value}")

    env_file.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")


def write_config_for_provider(project_root: Path, provider: Mapping[str, str]) -> None:
    """Write config.yaml with the selected provider while preserving path dirs."""

    config_path = project_root / "config.yaml"
    sections = read_simple_yaml_sections(config_path)
    paths = sections.get("paths", {})
    app = sections.get("app", {})
    teaching = sections.get("teaching", {})

    data_dir = paths.get("data_dir", "./data")
    logs_dir = paths.get("logs_dir", "./logs")
    user_id = app.get("user_id", "default_user")
    prompt_mode = teaching.get("prompt_mode", "split")

    content = f"""# Teacher-skill 配置文件
# 首次使用推荐运行：python main.py --setup

llm:
  provider: "{provider['provider']}"
  api_format: "{provider['api_format']}"
  base_url: "{provider['base_url']}"
  model_id: "{provider['model_id']}"
  temperature: 0.7
  max_tokens: 2048
  analysis_max_tokens: 4096
  judgment_max_tokens: 1024
  onboarding_max_tokens: 512
  retry_count: 3
  timeout: 30

teaching:
  hint_max_level: 4
  enable_rewards: true
  enable_persona: false
  prompt_mode: "{prompt_mode}"

paths:
  data_dir: "{data_dir}"
  logs_dir: "{logs_dir}"

app:
  user_id: "{user_id}"
"""
    config_path.write_text(content, encoding="utf-8")


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


def render_setup_wizard(
    project_root: Path,
    *,
    output_console,
    table_cls,
    panel_cls,
) -> bool:
    """Render the compact first-time setup wizard."""

    actions, is_ok = run_setup_wizard(
        project_root,
        input_func=output_console.input,
    )
    table = table_cls(title="首次配置向导")
    table.add_column("项目", style="cyan")
    table.add_column("状态", width=10)
    table.add_column("说明", style="white")

    for action in actions:
        status = action["status"]
        if status in ("已创建", "已准备", "可用", "已配置"):
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
                "[bold green]配置完成。[/bold green]\n\n"
                "现在可以直接运行：\n"
                "[green]python main.py --demo[/green]\n"
                "或：\n"
                "[green]python main.py --file samples/sample_article.md[/green]\n\n"
                "需要复检时运行：[green]python main.py --check[/green]",
                border_style="green",
            )
        )
    else:
        output_console.print(
            panel_cls.fit(
                "[bold yellow]配置未完成。[/bold yellow]\n\n"
                "请重新运行 `python main.py --setup`，选择服务商并粘贴 API Key。",
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
