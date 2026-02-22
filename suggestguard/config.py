"""Configuration management for SuggestGuard."""

from __future__ import annotations

import logging
import os
import re
from copy import deepcopy
from pathlib import Path

import yaml

from suggestguard.database import Database

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict = {
    "brands": [],
    "notifications": {
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        "slack": {"enabled": False, "webhook_url": ""},
    },
    "settings": {
        "database": "suggestguard.db",
        "request_delay": 1.5,
        "max_workers": 3,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
}

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env(value: str) -> str:
    """Replace ${ENV_VAR} patterns with environment variable values."""

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return _ENV_PATTERN.sub(_replacer, value)


def _resolve_env_recursive(obj: object) -> object:
    """Walk a nested dict/list and resolve all ${ENV_VAR} strings."""
    if isinstance(obj, str):
        return _resolve_env(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_recursive(item) for item in obj]
    return obj


class SuggestGuardConfig:
    """YAML-based configuration manager."""

    def __init__(self, config_path: str = "suggestguard.yml") -> None:
        self.config_path = Path(config_path)
        self.data: dict = deepcopy(DEFAULT_CONFIG)

    # ── persistence ──────────────────────────────────────────────────

    def load(self) -> None:
        """Load config from YAML file and resolve env variables."""
        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
        self.data = self._merge(deepcopy(DEFAULT_CONFIG), raw)
        self.data = _resolve_env_recursive(self.data)

    def save(self) -> None:
        """Write current config to YAML file."""
        self.config_path.write_text(
            yaml.dump(self.data, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def init_config(self) -> None:
        """Create config file with defaults if it doesn't exist, then validate."""
        if not self.config_path.exists():
            self.data = deepcopy(DEFAULT_CONFIG)
            self.save()
        self.load()
        errors = self.validate()
        for err in errors:
            logger.warning("Config validation: %s", err)

    # ── access ───────────────────────────────────────────────────────

    def get(self, key: str, default: object = None) -> object:
        """Dotted-path access: config.get('settings.request_delay')."""
        parts = key.split(".")
        node = self.data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    # ── validation ───────────────────────────────────────────────────

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty = valid)."""
        errors: list[str] = []

        tg = self.get("notifications.telegram", {})
        if tg.get("enabled"):
            if not tg.get("bot_token"):
                errors.append(
                    "notifications.telegram.bot_token is required when Telegram is enabled"
                )
            if not tg.get("chat_id"):
                errors.append("notifications.telegram.chat_id is required when Telegram is enabled")

        slack = self.get("notifications.slack", {})
        if slack.get("enabled"):
            if not slack.get("webhook_url"):
                errors.append("notifications.slack.webhook_url is required when Slack is enabled")

        delay = self.get("settings.request_delay")
        if not isinstance(delay, (int, float)) or delay < 0:
            errors.append("settings.request_delay must be a non-negative number")

        workers = self.get("settings.max_workers")
        if not isinstance(workers, int) or workers < 1:
            errors.append("settings.max_workers must be a positive integer")

        return errors

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _merge(base: dict, override: dict) -> dict:
        """Deep-merge *override* into *base*, returning a new dict."""
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = SuggestGuardConfig._merge(merged[key], value)
            else:
                merged[key] = value
        return merged


# ── module-level helper ──────────────────────────────────────────────


def _connect_db(db_path: str) -> Database:
    """Create and connect a Database (plain helper, no caching)."""
    db = Database(db_path)
    db.connect()
    return db


def get_db(config_path: str = "suggestguard.yml") -> Database:
    """Return a connected Database instance.

    When running inside a Streamlit app, the connection is cached via
    ``st.cache_resource`` so that every rerun reuses the same object.
    Outside Streamlit the function simply creates a new connection.
    """
    cfg = SuggestGuardConfig(config_path)
    cfg.init_config()
    db_path = cfg.get("settings.database", "suggestguard.db")

    try:
        import streamlit as st

        if st.runtime.exists():

            @st.cache_resource
            def _cached_db(path: str) -> Database:
                return _connect_db(path)

            return _cached_db(db_path)
    except (ImportError, AttributeError):
        pass

    return _connect_db(db_path)
