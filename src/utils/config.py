"""集中配置管理 — 所有可调参数从此处读取，代码中不再硬编码。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM client parameters."""

    model_id: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 2048
    analysis_max_tokens: int = 4096
    judgment_max_tokens: int = 1024
    onboarding_max_tokens: int = 512
    retry_count: int = 3
    timeout: int = 30


class TeachingConfig(BaseModel):
    """Teaching behaviour parameters."""

    hint_max_level: int = 4
    enable_rewards: bool = True
    enable_persona: bool = False
    prompt_mode: str = "split"  # "merged" or "split"


class PathsConfig(BaseModel):
    """Filesystem paths."""

    data_dir: str = "./data"
    logs_dir: str = "./logs"

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def logs_path(self) -> Path:
        return Path(self.logs_dir)


class AppConfig(BaseModel):
    """Application-level settings."""

    user_id: str = "default_user"


class Config(BaseModel):
    """Root configuration object."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    teaching: TeachingConfig = Field(default_factory=TeachingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    app: AppConfig = Field(default_factory=AppConfig)


# ─── Singleton loader ───

_CONFIG: Optional[Config] = None
_CONFIG_PATH: Optional[Path] = None


def load_config(config_path: Optional[Path | str] = None, force_reload: bool = False) -> Config:
    """Load configuration from YAML file (or use defaults if file missing).

    The result is cached; subsequent calls return the same instance unless
    ``force_reload=True`` is passed.
    """
    global _CONFIG, _CONFIG_PATH

    if _CONFIG is not None and not force_reload:
        return _CONFIG

    if config_path is None:
        config_path = Path("config.yaml")
    else:
        config_path = Path(config_path)

    _CONFIG_PATH = config_path

    # Start with defaults
    cfg = Config()

    # Override from YAML if present
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if raw and isinstance(raw, dict):
            cfg = Config(**raw)

    _CONFIG = cfg
    return cfg


def get_config() -> Config:
    """Return the currently-loaded configuration singleton.

    Calls ``load_config()`` implicitly on first use.
    """
    if _CONFIG is None:
        return load_config()
    return _CONFIG


# Convenience module-level accessor (lazy-loaded)
@property
def config() -> Config:
    return get_config()
