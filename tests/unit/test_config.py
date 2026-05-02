"""Tests for src/utils/config.py."""

import pytest

import src.utils.config as config_module
from src.utils.config import load_config, get_config, Config


@pytest.fixture(autouse=True)
def reset_config_singleton(monkeypatch):
    """Reset the global config singleton before each test."""
    monkeypatch.setattr(config_module, "_CONFIG", None)
    monkeypatch.setattr(config_module, "_CONFIG_PATH", None)


class TestLoadConfig:
    """Tests for load_config."""

    def test_default_values(self, tmp_path):
        cfg = load_config(config_path=tmp_path / "nonexistent.yaml")
        assert cfg.llm.model_id == "claude-sonnet-4-20250514"
        assert cfg.llm.temperature == 0.7
        assert cfg.llm.max_tokens == 2048
        assert cfg.llm.timeout == 30
        assert cfg.llm.retry_count == 3
        assert cfg.teaching.prompt_mode == "split"
        assert cfg.teaching.hint_max_level == 4
        assert cfg.teaching.enable_rewards is True
        assert cfg.paths.data_dir == "./data"
        assert cfg.paths.logs_dir == "./logs"
        assert cfg.app.user_id == "default_user"

    def test_yaml_override(self, tmp_path):
        p = tmp_path / "test_config.yaml"
        p.write_text(
            "llm:\n  timeout: 60\n  retry_count: 5\n"
            "teaching:\n  prompt_mode: merged\n",
            encoding="utf-8",
        )
        cfg = load_config(config_path=p)
        assert cfg.llm.timeout == 60
        assert cfg.llm.retry_count == 5
        assert cfg.teaching.prompt_mode == "merged"
        # unchanged values
        assert cfg.llm.model_id == "claude-sonnet-4-20250514"
        assert cfg.teaching.hint_max_level == 4

    def test_force_reload(self, tmp_path):
        p = tmp_path / "test_config.yaml"
        p.write_text("llm:\n  timeout: 60\n", encoding="utf-8")
        cfg1 = load_config(config_path=p)
        assert cfg1.llm.timeout == 60

        p.write_text("llm:\n  timeout: 90\n", encoding="utf-8")
        cfg2 = load_config(config_path=p)
        assert cfg2.llm.timeout == 60  # cached

        cfg3 = load_config(config_path=p, force_reload=True)
        assert cfg3.llm.timeout == 90

    def test_empty_yaml_uses_defaults(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        cfg = load_config(config_path=p)
        assert cfg.llm.timeout == 30


class TestGetConfig:
    """Tests for get_config singleton accessor."""

    def test_returns_loaded_config(self, tmp_path, monkeypatch):
        p = tmp_path / "cfg.yaml"
        p.write_text("app:\n  user_id: testuser\n", encoding="utf-8")
        cfg = load_config(config_path=p)
        # get_config should return the same instance
        assert get_config() is cfg

    def test_implicit_load(self, tmp_path, monkeypatch):
        # Ensure singleton is reset by fixture
        p = tmp_path / "cfg.yaml"
        p.write_text("app:\n  user_id: implicit\n", encoding="utf-8")
        # Monkeypatch the default path resolution so get_config uses our file
        monkeypatch.setattr(
            config_module, "load_config",
            lambda config_path=p, force_reload=False: load_config(config_path=config_path)
        )
        cfg = get_config()
        assert cfg.app.user_id == "implicit"
