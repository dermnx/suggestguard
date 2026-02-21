"""Tests for suggestguard.scanner (mocked collector, no real requests)."""

from __future__ import annotations

import json

import pytest

from suggestguard.database import Database
from suggestguard.scanner import ScanEngine

# ── helpers ──────────────────────────────────────────────────────────


class FakeConfig:
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


class FakeCollector:
    """Replaces AutocompleteCollector — returns canned suggestions."""

    def __init__(self, responses: dict[str, list[str]] | None = None) -> None:
        self._responses = responses or {}
        self.closed = False

    async def collect_brand(self, brand, progress_callback=None):
        keywords = (
            json.loads(brand["keywords"])
            if isinstance(brand["keywords"], str)
            else brand["keywords"]
        )
        results = []
        for kw in keywords:
            suggestions = self._responses.get(kw, [])
            results.append(
                {
                    "query": kw,
                    "suggestions": suggestions,
                    "source": "autocomplete",
                    "timestamp": "2025-01-01 12:00:00",
                }
            )
        if progress_callback:
            progress_callback(len(results), len(results), keywords[-1])
        return results

    async def close(self):
        self.closed = True


def _make_db() -> Database:
    """Create an in-memory DB with schema ready."""
    db = Database(":memory:")
    db.connect()
    return db


def _add_test_brand(
    db: Database, name: str = "TestMarka", keywords: list[str] | None = None
) -> dict:
    """Insert a brand and return its dict."""
    kw = keywords or ["testmarka"]
    brand_id = db.add_brand(name, kw)
    return db.get_brand(brand_id)


# ── ScanEngine.scan_brand ────────────────────────────────────────────


class TestScanBrand:
    @pytest.mark.asyncio
    async def test_basic_scan(self):
        db = _make_db()
        brand = _add_test_brand(db)
        config = FakeConfig()
        engine = ScanEngine(db, config)

        fake = FakeCollector(
            {
                "testmarka": [
                    "testmarka nedir",
                    "testmarka güvenilir mi",
                    "testmarka dolandırıcı",
                ]
            }
        )
        engine._collector = fake

        report = await engine.scan_brand(brand)

        assert report["brand_name"] == "TestMarka"
        assert report["total_suggestions"] == 3
        assert report["snapshot_id"] is not None
        assert report["summary"]["total"] == 3
        assert report["summary"]["negative"] >= 1  # dolandırıcı

        # DB should have snapshot + suggestions
        snap = db.get_latest_snapshot(brand["id"])
        assert snap is not None
        suggestions = db.get_suggestions_for_brand(brand["id"])
        assert len(suggestions) == 3

        await engine.close()
        db.close()

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """Duplicate suggestion texts across queries should be merged."""
        db = _make_db()
        brand = _add_test_brand(db, keywords=["marka"])
        config = FakeConfig()
        engine = ScanEngine(db, config)

        fake = FakeCollector(
            {
                "marka": [
                    "marka nedir",
                    "marka nedir",  # exact duplicate
                    "marka iletişim",
                ]
            }
        )
        engine._collector = fake

        report = await engine.scan_brand(brand)
        assert report["total_suggestions"] == 2  # deduplicated
        await engine.close()
        db.close()

    @pytest.mark.asyncio
    async def test_sentiment_stored_in_db(self):
        db = _make_db()
        brand = _add_test_brand(db)
        config = FakeConfig()
        engine = ScanEngine(db, config)

        fake = FakeCollector({"testmarka": ["testmarka dolandırıcı", "testmarka en iyi"]})
        engine._collector = fake

        await engine.scan_brand(brand)

        suggestions = db.get_suggestions_for_brand(brand["id"])
        sentiments = {s["text"]: s["sentiment"] for s in suggestions}
        assert sentiments["testmarka dolandırıcı"] == "negative"
        assert sentiments["testmarka en iyi"] == "positive"

        await engine.close()
        db.close()

    @pytest.mark.asyncio
    async def test_diff_on_second_scan(self):
        """Second scan should detect new and disappeared suggestions."""
        db = _make_db()
        brand = _add_test_brand(db)
        config = FakeConfig()
        engine = ScanEngine(db, config)

        # First scan
        fake1 = FakeCollector({"testmarka": ["testmarka nedir", "testmarka fiyat"]})
        engine._collector = fake1
        report1 = await engine.scan_brand(brand)
        assert report1["diff"]["total_previous"] == 0  # no previous
        assert report1["diff"]["new_count"] == 2

        # Second scan — one new, one gone
        fake2 = FakeCollector({"testmarka": ["testmarka nedir", "testmarka şikayet"]})
        engine._collector = fake2
        report2 = await engine.scan_brand(brand)
        assert report2["diff"]["new_count"] == 1  # "testmarka şikayet"
        assert report2["diff"]["disappeared_count"] == 1  # "testmarka fiyat"

        await engine.close()
        db.close()

    @pytest.mark.asyncio
    async def test_progress_callback_called(self):
        db = _make_db()
        brand = _add_test_brand(db)
        config = FakeConfig()
        engine = ScanEngine(db, config)

        calls = []
        fake = FakeCollector({"testmarka": ["testmarka nedir"]})
        engine._collector = fake

        await engine.scan_brand(brand, progress_callback=lambda c, t, q: calls.append((c, t, q)))
        assert len(calls) > 0

        await engine.close()
        db.close()

    @pytest.mark.asyncio
    async def test_empty_suggestions(self):
        db = _make_db()
        brand = _add_test_brand(db)
        config = FakeConfig()
        engine = ScanEngine(db, config)

        fake = FakeCollector({"testmarka": []})
        engine._collector = fake

        report = await engine.scan_brand(brand)
        assert report["total_suggestions"] == 0
        assert report["summary"]["total"] == 0

        await engine.close()
        db.close()


# ── ScanEngine.scan_all ──────────────────────────────────────────────


class TestScanAll:
    @pytest.mark.asyncio
    async def test_scan_all_active_brands(self):
        db = _make_db()
        _add_test_brand(db, "Marka1", ["marka1"])
        _add_test_brand(db, "Marka2", ["marka2"])

        config = FakeConfig()
        engine = ScanEngine(db, config)
        fake = FakeCollector(
            {
                "marka1": ["marka1 nedir"],
                "marka2": ["marka2 nedir", "marka2 sorun"],
            }
        )
        engine._collector = fake

        reports = await engine.scan_all()
        assert len(reports) == 2
        names = {r["brand_name"] for r in reports}
        assert names == {"Marka1", "Marka2"}

        await engine.close()
        db.close()

    @pytest.mark.asyncio
    async def test_scan_all_skips_inactive(self):
        db = _make_db()
        _add_test_brand(db, "Active", ["active"])
        inactive = _add_test_brand(db, "Inactive", ["inactive"])
        db.deactivate_brand(inactive["id"])

        config = FakeConfig()
        engine = ScanEngine(db, config)
        fake = FakeCollector({"active": ["active nedir"]})
        engine._collector = fake

        reports = await engine.scan_all()
        assert len(reports) == 1
        assert reports[0]["brand_name"] == "Active"

        await engine.close()
        db.close()

    @pytest.mark.asyncio
    async def test_scan_all_progress_callback(self):
        db = _make_db()
        _add_test_brand(db, "A", ["a"])
        _add_test_brand(db, "B", ["b"])

        calls = []
        config = FakeConfig()
        engine = ScanEngine(db, config)
        fake = FakeCollector({"a": ["a nedir"], "b": ["b nedir"]})
        engine._collector = fake

        await engine.scan_all(progress_callback=lambda c, t, n: calls.append((c, t, n)))
        assert len(calls) == 2
        assert calls[0][1] == 2  # total brands = 2
        assert calls[1][1] == 2

        await engine.close()
        db.close()


# ── ScanEngine.get_scan_estimate ─────────────────────────────────────


class TestGetScanEstimate:
    def test_estimate_with_az_expansion(self):
        db = _make_db()
        brand = _add_test_brand(db, "TestBrand", ["test"])
        config = FakeConfig()
        engine = ScanEngine(db, config)

        est = engine.get_scan_estimate(brand)
        assert est["total_queries"] > 0
        assert est["estimated_seconds"] >= 0
        db.close()

    def test_estimate_without_expansion(self):
        db = _make_db()
        brand_id = db.add_brand("NoExpand", ["noexpand"], expand_az=False, expand_turkish=False)
        brand = db.get_brand(brand_id)
        config = FakeConfig()
        engine = ScanEngine(db, config)

        est = engine.get_scan_estimate(brand)
        # Without expansion: just base + ascii variant (if different)
        assert est["total_queries"] >= 1
        assert est["total_queries"] < 10  # no a-z expansion
        db.close()

    def test_estimate_multiple_keywords(self):
        db = _make_db()
        brand = _add_test_brand(db, "Multi", ["foo", "bar"])
        config = FakeConfig()
        engine = ScanEngine(db, config)

        est = engine.get_scan_estimate(brand)
        # 2 keywords each with a-z + turkish expansion
        assert est["total_queries"] > 10
        db.close()

    def test_estimate_seconds_formula(self):
        db = _make_db()
        brand = _add_test_brand(db, "Formula", ["xyz"])
        config = FakeConfig(
            {
                "settings": {
                    "request_delay": 2.0,
                    "max_workers": 2,
                    "user_agent": "Test",
                },
                "notifications": {
                    "telegram": {"enabled": False},
                    "slack": {"enabled": False},
                },
            }
        )
        engine = ScanEngine(db, config)

        est = engine.get_scan_estimate(brand)
        # estimated = (total / workers) * delay = (total / 2) * 2.0 = total
        assert est["estimated_seconds"] == float(est["total_queries"])
        db.close()


# ── notifications on new negatives ───────────────────────────────────


class TestNotifications:
    @pytest.mark.asyncio
    async def test_no_notification_when_no_negatives(self):
        db = _make_db()
        brand = _add_test_brand(db)
        config = FakeConfig()
        engine = ScanEngine(db, config)

        fake = FakeCollector({"testmarka": ["testmarka nedir"]})
        engine._collector = fake

        report = await engine.scan_brand(brand)
        assert report["new_negatives"] == 0

        await engine.close()
        db.close()

    @pytest.mark.asyncio
    async def test_new_negatives_counted(self):
        db = _make_db()
        brand = _add_test_brand(db)
        config = FakeConfig()
        engine = ScanEngine(db, config)

        fake = FakeCollector({"testmarka": ["testmarka dolandırıcı", "testmarka sahte"]})
        engine._collector = fake

        report = await engine.scan_brand(brand)
        # First scan: all are new, negatives should be counted
        assert report["new_negatives"] == 2

        await engine.close()
        db.close()


# ── engine lifecycle ─────────────────────────────────────────────────


class TestEngineLifecycle:
    @pytest.mark.asyncio
    async def test_close_with_collector(self):
        db = _make_db()
        config = FakeConfig()
        engine = ScanEngine(db, config)

        fake = FakeCollector()
        engine._collector = fake

        await engine.close()
        assert fake.closed is True
        assert engine._collector is None
        db.close()

    @pytest.mark.asyncio
    async def test_close_without_collector(self):
        db = _make_db()
        config = FakeConfig()
        engine = ScanEngine(db, config)

        await engine.close()  # should not raise
        assert engine._collector is None
        db.close()

    def test_get_collector_creates_instance(self):
        db = _make_db()
        config = FakeConfig()
        engine = ScanEngine(db, config)

        collector = engine._get_collector()
        assert collector is not None
        assert collector.request_delay == 0
        assert collector.max_workers == 2
        db.close()
