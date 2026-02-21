"""Tests for suggestguard.config module."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from suggestguard.config import (
    DEFAULT_CONFIG,
    SuggestGuardConfig,
    _resolve_env,
    _resolve_env_recursive,
    get_db,
)


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Return a path for a config file inside a temp directory."""
    return tmp_path / "suggestguard.yml"


@pytest.fixture
def cfg(config_file: Path) -> SuggestGuardConfig:
    """Return a SuggestGuardConfig pointed at a temp file (not yet saved)."""
    return SuggestGuardConfig(str(config_file))


# ── init_config / load / save ────────────────────────────────────────


class TestPersistence:
    def test_init_config_creates_file(self, cfg: SuggestGuardConfig, config_file: Path):
        assert not config_file.exists()
        cfg.init_config()
        assert config_file.exists()

    def test_init_config_loads_defaults(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        assert cfg.get("settings.database") == "suggestguard.db"
        assert cfg.get("settings.request_delay") == 1.5
        assert cfg.get("settings.max_workers") == 3

    def test_init_config_preserves_existing(self, cfg: SuggestGuardConfig, config_file: Path):
        config_file.write_text(
            yaml.dump({"settings": {"database": "custom.db"}}),
            encoding="utf-8",
        )
        cfg.init_config()
        assert cfg.get("settings.database") == "custom.db"
        # merged defaults still present
        assert cfg.get("settings.request_delay") == 1.5

    def test_save_roundtrip(self, cfg: SuggestGuardConfig, config_file: Path):
        cfg.init_config()
        cfg.data["settings"]["database"] = "changed.db"
        cfg.save()

        cfg2 = SuggestGuardConfig(str(config_file))
        cfg2.load()
        assert cfg2.get("settings.database") == "changed.db"

    def test_load_empty_file(self, cfg: SuggestGuardConfig, config_file: Path):
        config_file.write_text("", encoding="utf-8")
        cfg.load()
        # should fall back to defaults
        assert cfg.get("settings.database") == "suggestguard.db"

    def test_load_partial_override(self, cfg: SuggestGuardConfig, config_file: Path):
        config_file.write_text(
            yaml.dump({"notifications": {"telegram": {"enabled": True, "bot_token": "abc"}}}),
            encoding="utf-8",
        )
        cfg.load()
        assert cfg.get("notifications.telegram.enabled") is True
        assert cfg.get("notifications.telegram.bot_token") == "abc"
        # chat_id should still have its default
        assert cfg.get("notifications.telegram.chat_id") == ""


# ── dotted get ───────────────────────────────────────────────────────


class TestGet:
    def test_get_top_level(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        assert isinstance(cfg.get("brands"), list)

    def test_get_nested(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        assert cfg.get("notifications.slack.enabled") is False

    def test_get_missing_returns_default(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        assert cfg.get("nonexistent.key") is None
        assert cfg.get("nonexistent.key", 42) == 42

    def test_get_partial_path(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        result = cfg.get("notifications.telegram")
        assert isinstance(result, dict)
        assert "bot_token" in result


# ── env var resolution ───────────────────────────────────────────────


class TestEnvResolution:
    def test_resolve_single_var(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        assert _resolve_env("${MY_TOKEN}") == "secret123"

    def test_resolve_unset_var_unchanged(self):
        assert _resolve_env("${DEFINITELY_NOT_SET_XYZ}") == "${DEFINITELY_NOT_SET_XYZ}"

    def test_resolve_mixed_text(self, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        assert _resolve_env("http://${HOST}:8080") == "http://localhost:8080"

    def test_resolve_multiple_vars(self, monkeypatch):
        monkeypatch.setenv("A", "1")
        monkeypatch.setenv("B", "2")
        assert _resolve_env("${A}-${B}") == "1-2"

    def test_resolve_no_vars(self):
        assert _resolve_env("plain text") == "plain text"

    def test_resolve_recursive_dict(self, monkeypatch):
        monkeypatch.setenv("TG_TOKEN", "bot123")
        data = {"telegram": {"bot_token": "${TG_TOKEN}", "chat_id": "fixed"}}
        resolved = _resolve_env_recursive(data)
        assert resolved["telegram"]["bot_token"] == "bot123"
        assert resolved["telegram"]["chat_id"] == "fixed"

    def test_resolve_recursive_list(self, monkeypatch):
        monkeypatch.setenv("BRAND", "acme")
        data = ["${BRAND}", "other"]
        resolved = _resolve_env_recursive(data)
        assert resolved == ["acme", "other"]

    def test_resolve_recursive_non_string(self):
        assert _resolve_env_recursive(42) == 42
        assert _resolve_env_recursive(True) is True

    def test_config_resolves_env_on_load(
        self, cfg: SuggestGuardConfig, config_file: Path, monkeypatch
    ):
        monkeypatch.setenv("SG_BOT_TOKEN", "from_env")
        config_file.write_text(
            yaml.dump(
                {
                    "notifications": {
                        "telegram": {
                            "enabled": True,
                            "bot_token": "${SG_BOT_TOKEN}",
                            "chat_id": "123",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        cfg.load()
        assert cfg.get("notifications.telegram.bot_token") == "from_env"


# ── validation ───────────────────────────────────────────────────────


class TestValidation:
    def test_valid_defaults(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        assert cfg.validate() == []

    def test_telegram_enabled_no_token(self, cfg: SuggestGuardConfig, config_file: Path):
        config_file.write_text(
            yaml.dump({"notifications": {"telegram": {"enabled": True}}}),
            encoding="utf-8",
        )
        cfg.load()
        errors = cfg.validate()
        assert any("bot_token" in e for e in errors)
        assert any("chat_id" in e for e in errors)

    def test_telegram_enabled_with_token(self, cfg: SuggestGuardConfig, config_file: Path):
        config_file.write_text(
            yaml.dump(
                {
                    "notifications": {
                        "telegram": {"enabled": True, "bot_token": "tok", "chat_id": "123"}
                    }
                }
            ),
            encoding="utf-8",
        )
        cfg.load()
        errors = cfg.validate()
        telegram_errors = [e for e in errors if "telegram" in e]
        assert telegram_errors == []

    def test_slack_enabled_no_url(self, cfg: SuggestGuardConfig, config_file: Path):
        config_file.write_text(
            yaml.dump({"notifications": {"slack": {"enabled": True}}}),
            encoding="utf-8",
        )
        cfg.load()
        errors = cfg.validate()
        assert any("webhook_url" in e for e in errors)

    def test_invalid_request_delay(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        cfg.data["settings"]["request_delay"] = -1
        errors = cfg.validate()
        assert any("request_delay" in e for e in errors)

    def test_invalid_max_workers(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        cfg.data["settings"]["max_workers"] = 0
        errors = cfg.validate()
        assert any("max_workers" in e for e in errors)

    def test_non_int_max_workers(self, cfg: SuggestGuardConfig):
        cfg.init_config()
        cfg.data["settings"]["max_workers"] = 2.5
        errors = cfg.validate()
        assert any("max_workers" in e for e in errors)


# ── deep merge ───────────────────────────────────────────────────────


class TestMerge:
    def test_merge_adds_new_keys(self):
        base = {"a": 1}
        override = {"b": 2}
        result = SuggestGuardConfig._merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_merge_overrides_scalar(self):
        base = {"a": 1}
        override = {"a": 99}
        result = SuggestGuardConfig._merge(base, override)
        assert result == {"a": 99}

    def test_merge_deep_dict(self):
        base = {"nested": {"x": 1, "y": 2}}
        override = {"nested": {"y": 99, "z": 3}}
        result = SuggestGuardConfig._merge(base, override)
        assert result == {"nested": {"x": 1, "y": 99, "z": 3}}

    def test_merge_does_not_mutate_base(self):
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        SuggestGuardConfig._merge(base, override)
        assert base == {"a": {"b": 1}}


# ── get_db ───────────────────────────────────────────────────────────


class TestGetDb:
    def test_get_db_creates_database(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "suggestguard.yml"
        config_file.write_text(
            yaml.dump({"settings": {"database": str(tmp_path / "test.db")}}),
            encoding="utf-8",
        )
        db = get_db(str(config_file))
        assert db.conn is not None
        # should be able to query
        db.add_brand("TestBrand", ["test"])
        assert db.get_brand_by_name("TestBrand") is not None
        db.close()

    def test_get_db_default_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = get_db(str(tmp_path / "suggestguard.yml"))
        assert db.conn is not None
        db.close()


# ── DEFAULT_CONFIG integrity ─────────────────────────────────────────


class TestDefaultConfig:
    def test_structure(self):
        assert "brands" in DEFAULT_CONFIG
        assert "notifications" in DEFAULT_CONFIG
        assert "settings" in DEFAULT_CONFIG

    def test_notifications_keys(self):
        assert "telegram" in DEFAULT_CONFIG["notifications"]
        assert "slack" in DEFAULT_CONFIG["notifications"]

    def test_settings_keys(self):
        s = DEFAULT_CONFIG["settings"]
        assert s["database"] == "suggestguard.db"
        assert s["request_delay"] == 1.5
        assert s["max_workers"] == 3
        assert "user_agent" in s
