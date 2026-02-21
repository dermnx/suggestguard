"""Shared fixtures for the suggestguard test suite."""

from __future__ import annotations

import pytest

from suggestguard.database import Database

# ── database fixtures ─────────────────────────────────────────────────


@pytest.fixture
def tmp_db():
    """In-memory database, connected and ready."""
    db = Database(":memory:")
    db.connect()
    yield db
    db.close()


# ── config fixture ────────────────────────────────────────────────────


class _FakeConfig:
    """Minimal config stub supporting dotted get()."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = data or {
            "settings": {
                "request_delay": 0,
                "max_workers": 2,
                "user_agent": "TestAgent",
            },
            "notifications": {
                "telegram": {"enabled": False},
                "slack": {"enabled": False},
            },
        }

    def get(self, key: str, default=None):
        parts = key.split(".")
        node = self._data
        for p in parts:
            if isinstance(node, dict) and p in node:
                node = node[p]
            else:
                return default
        return node


@pytest.fixture
def tmp_config():
    """Return a FakeConfig with sensible defaults for testing."""
    return _FakeConfig()


# ── brand / suggestion fixtures ───────────────────────────────────────


@pytest.fixture
def sample_brand(tmp_db: Database) -> dict:
    """Insert a sample brand and return its dict."""
    brand_id = tmp_db.add_brand("TestMarka", ["testmarka"])
    return tmp_db.get_brand(brand_id)


_SAMPLE_SUGGESTIONS = [
    ("testmarka dolandırıcı", "negative", -0.9, "fraud"),
    ("testmarka şikayet", "negative", -0.6, "complaint"),
    ("testmarka en iyi", "positive", 0.6, None),
    ("testmarka güvenilir", "positive", 0.6, None),
    ("testmarka nedir", "neutral", 0.0, None),
    ("testmarka iletişim", "neutral", 0.0, None),
    ("testmarka fiyat", "neutral", 0.0, None),
]


@pytest.fixture
def sample_suggestions() -> list[tuple]:
    """Return a list of (text, sentiment, score, category) tuples."""
    return list(_SAMPLE_SUGGESTIONS)


@pytest.fixture
def seeded_db(tmp_db: Database) -> Database:
    """Database pre-loaded with one brand, one snapshot, and sample suggestions."""
    brand_id = tmp_db.add_brand("TestMarka", ["testmarka"])
    snapshot_id = tmp_db.add_snapshot(brand_id, "autocomplete", "testmarka", [])

    for i, (text, sentiment, score, category) in enumerate(_SAMPLE_SUGGESTIONS):
        tmp_db.upsert_suggestion(
            snapshot_id,
            brand_id,
            text,
            i + 1,
            sentiment,
            score,
            category,
        )

    return tmp_db
