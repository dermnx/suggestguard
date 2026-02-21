"""End-to-end integration tests.

Flow: add brand → scan (mock collector) → analyse → save → second scan → diff.
"""

from __future__ import annotations

import json

import pytest

from suggestguard.analyzers.diff import DiffAnalyzer
from suggestguard.analyzers.sentiment import SentimentAnalyzer
from suggestguard.database import Database
from suggestguard.scanner import ScanEngine

# ── helpers ───────────────────────────────────────────────────────────


class _FakeConfig:
    """Minimal config stub."""

    def __init__(self) -> None:
        self._data = {
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


class _FakeCollector:
    """Returns canned suggestions per keyword."""

    def __init__(self, responses: dict[str, list[str]]) -> None:
        self._responses = responses
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


def _make_engine(db: Database) -> ScanEngine:
    return ScanEngine(db, _FakeConfig())


# ── full lifecycle ────────────────────────────────────────────────────


class TestFullScanLifecycle:
    """Brand → scan → analyse → save → second scan → diff."""

    @pytest.mark.asyncio
    async def test_full_flow(self, tmp_db: Database):
        # 1. Add brand
        brand_id = tmp_db.add_brand("IntegrationBrand", ["integrationbrand"])
        brand = tmp_db.get_brand(brand_id)
        assert brand is not None

        engine = _make_engine(tmp_db)

        # 2. First scan — 4 suggestions
        engine._collector = _FakeCollector(
            {
                "integrationbrand": [
                    "integrationbrand nedir",
                    "integrationbrand dolandırıcı",
                    "integrationbrand iletişim",
                    "integrationbrand en iyi",
                ]
            }
        )

        report1 = await engine.scan_brand(brand)

        assert report1["brand_name"] == "IntegrationBrand"
        assert report1["total_suggestions"] == 4
        assert report1["snapshot_id"] is not None
        assert report1["summary"]["total"] == 4
        assert report1["summary"]["negative"] >= 1  # dolandırıcı

        # First scan diff: all are new
        assert report1["diff"]["new_count"] == 4
        assert report1["diff"]["total_previous"] == 0

        # Verify DB state
        snap1 = tmp_db.get_latest_snapshot(brand_id)
        assert snap1 is not None
        suggestions1 = tmp_db.get_suggestions_for_brand(brand_id)
        assert len(suggestions1) == 4

        # Verify sentiment was stored
        sentiments = {s["text"]: s["sentiment"] for s in suggestions1}
        assert sentiments["integrationbrand dolandırıcı"] == "negative"
        assert sentiments["integrationbrand en iyi"] == "positive"

        # 3. Second scan — one gone, one new
        engine._collector = _FakeCollector(
            {
                "integrationbrand": [
                    "integrationbrand nedir",
                    "integrationbrand iletişim",
                    "integrationbrand en iyi",
                    "integrationbrand şikayet",  # new negative
                ]
            }
        )

        report2 = await engine.scan_brand(brand)

        assert report2["total_suggestions"] == 4
        assert report2["diff"]["new_count"] == 1  # şikayet
        assert report2["diff"]["disappeared_count"] == 1  # dolandırıcı
        assert report2["new_negatives"] >= 1  # şikayet is negative

        # Verify updated suggestions in DB
        suggestions2 = tmp_db.get_suggestions_for_brand(brand_id)
        texts2 = {s["text"] for s in suggestions2}
        assert "integrationbrand şikayet" in texts2

        # Verify upsert — existing suggestions were updated
        for s in suggestions2:
            if s["text"] == "integrationbrand nedir":
                assert s["times_seen"] >= 2

        await engine.close()

    @pytest.mark.asyncio
    async def test_empty_scan(self, tmp_db: Database):
        """Scan with no suggestions returned."""
        brand_id = tmp_db.add_brand("EmptyBrand", ["emptybrand"])
        brand = tmp_db.get_brand(brand_id)

        engine = _make_engine(tmp_db)
        engine._collector = _FakeCollector({"emptybrand": []})

        report = await engine.scan_brand(brand)

        assert report["total_suggestions"] == 0
        assert report["summary"]["total"] == 0
        assert report["new_negatives"] == 0

        await engine.close()


# ── brand management lifecycle ────────────────────────────────────────


class TestBrandManagement:
    def test_add_deactivate_reactivate(self, tmp_db: Database):
        bid = tmp_db.add_brand("LifecycleBrand", ["lifecycle"])
        brand = tmp_db.get_brand(bid)
        assert brand["active"] == 1

        tmp_db.deactivate_brand(bid)
        brand = tmp_db.get_brand(bid)
        assert brand["active"] == 0

        # Should not appear in active list
        active = tmp_db.list_brands(active_only=True)
        assert not any(b["id"] == bid for b in active)

        # Reactivate
        tmp_db.update_brand(bid, active=True)
        brand = tmp_db.get_brand(bid)
        assert brand["active"] == 1

    @pytest.mark.asyncio
    async def test_inactive_brand_skipped_in_scan_all(self, tmp_db: Database):
        tmp_db.add_brand("Active", ["active"])
        bid_inactive = tmp_db.add_brand("Inactive", ["inactive"])
        tmp_db.deactivate_brand(bid_inactive)

        engine = _make_engine(tmp_db)
        engine._collector = _FakeCollector({"active": ["active nedir"]})

        reports = await engine.scan_all()
        assert len(reports) == 1
        assert reports[0]["brand_name"] == "Active"

        await engine.close()


# ── campaign lifecycle ────────────────────────────────────────────────


class TestCampaignLifecycle:
    def test_create_and_end_campaign(self, tmp_db: Database):
        bid = tmp_db.add_brand("CampaignBrand", ["campaign"])
        cid = tmp_db.add_campaign(bid, "Test Campaign", notes="Some notes")
        assert cid is not None

        campaigns = tmp_db.list_campaigns(brand_id=bid)
        assert len(campaigns) == 1
        assert campaigns[0]["name"] == "Test Campaign"
        assert campaigns[0]["ended_at"] is None

        # End campaign
        tmp_db.end_campaign(cid)

        campaigns = tmp_db.list_campaigns(brand_id=bid)
        assert campaigns[0]["ended_at"] is not None

    def test_campaign_comparison(self, tmp_db: Database):
        bid = tmp_db.add_brand("CompBrand", ["comp"])

        # Add some suggestions before campaign
        sid1 = tmp_db.add_snapshot(bid, "autocomplete", "comp", [])
        tmp_db.upsert_suggestion(sid1, bid, "comp kötü", 1, "negative", -0.6)
        tmp_db.upsert_suggestion(sid1, bid, "comp iyi", 2, "positive", 0.6)
        tmp_db.upsert_suggestion(sid1, bid, "comp nedir", 3, "neutral", 0.0)

        # Start campaign
        cid = tmp_db.add_campaign(bid, "Improvement Campaign")

        comparison = tmp_db.get_campaign_comparison(cid)
        assert comparison is not None
        assert comparison["campaign"]["name"] == "Improvement Campaign"
        assert "before" in comparison
        assert "during" in comparison


# ── diff analysis integration ─────────────────────────────────────────


class TestDiffIntegration:
    def test_diff_with_real_db_data(self, tmp_db: Database):
        bid = tmp_db.add_brand("DiffBrand", ["diff"])

        # First snapshot
        sid1 = tmp_db.add_snapshot(bid, "autocomplete", "diff", [])
        tmp_db.upsert_suggestion(sid1, bid, "diff nedir", 1, "neutral", 0.0)
        tmp_db.upsert_suggestion(sid1, bid, "diff kötü", 2, "negative", -0.6)

        prev = [
            {"text": s["text"], "position": s["position"]}
            for s in tmp_db.get_suggestions_for_brand(bid)
        ]

        # Second snapshot
        sid2 = tmp_db.add_snapshot(bid, "autocomplete", "diff", [])
        tmp_db.upsert_suggestion(sid2, bid, "diff nedir", 1, "neutral", 0.0)
        tmp_db.upsert_suggestion(sid2, bid, "diff güzel", 2, "positive", 0.6)

        curr = [
            {"text": "diff nedir", "position": 1},
            {"text": "diff güzel", "position": 2},
        ]

        result = DiffAnalyzer.compare_snapshots(prev, curr)
        assert result["summary"]["new_count"] == 1  # "diff güzel"
        assert result["summary"]["disappeared_count"] == 1  # "diff kötü"
        assert result["summary"]["unchanged_count"] == 1  # "diff nedir"

    def test_trend_detection_with_db(self, tmp_db: Database):
        bid = tmp_db.add_brand("TrendBrand", ["trend"])
        sid = tmp_db.add_snapshot(bid, "autocomplete", "trend", [])

        # Persistent negative: upsert 3 times
        tmp_db.upsert_suggestion(sid, bid, "trend kötü", 1, "negative", -0.6)
        sid2 = tmp_db.add_snapshot(bid, "autocomplete", "trend", [])
        tmp_db.upsert_suggestion(sid2, bid, "trend kötü", 1, "negative", -0.6)
        sid3 = tmp_db.add_snapshot(bid, "autocomplete", "trend", [])
        tmp_db.upsert_suggestion(sid3, bid, "trend kötü", 1, "negative", -0.6)

        trends = DiffAnalyzer.detect_trends(bid, tmp_db)
        assert len(trends["persistent_negative"]) == 1
        assert trends["persistent_negative"][0]["text"] == "trend kötü"


# ── sentiment → DB round-trip ─────────────────────────────────────────


class TestSentimentRoundTrip:
    def test_analyze_and_store(self, tmp_db: Database):
        sa = SentimentAnalyzer()
        bid = tmp_db.add_brand("SentBrand", ["sent"])
        sid = tmp_db.add_snapshot(bid, "autocomplete", "sent", [])

        texts = ["sent dolandırıcı", "sent en iyi", "sent nedir"]
        analyses = sa.analyze_batch(texts, "SentBrand")

        for i, (text, analysis) in enumerate(zip(texts, analyses)):
            tmp_db.upsert_suggestion(
                sid,
                bid,
                text,
                i + 1,
                analysis["sentiment"],
                analysis["score"],
                analysis["category"],
            )

        stored = tmp_db.get_suggestions_for_brand(bid)
        assert len(stored) == 3

        sentiments = {s["text"]: s["sentiment"] for s in stored}
        assert sentiments["sent dolandırıcı"] == "negative"
        assert sentiments["sent en iyi"] == "positive"

    def test_summary_from_db(self, tmp_db: Database):
        sa = SentimentAnalyzer()
        bid = tmp_db.add_brand("SumBrand", ["sum"])
        sid = tmp_db.add_snapshot(bid, "autocomplete", "sum", [])

        texts = ["sum kötü", "sum şikayet", "sum en iyi", "sum nedir"]
        analyses = sa.analyze_batch(texts, "SumBrand")

        for i, (text, analysis) in enumerate(zip(texts, analyses)):
            tmp_db.upsert_suggestion(
                sid,
                bid,
                text,
                i + 1,
                analysis["sentiment"],
                analysis["score"],
                analysis["category"],
            )

        summary = sa.get_summary(analyses)
        assert summary["total"] == 4
        assert summary["negative"] >= 2  # kötü, şikayet
        assert summary["positive"] >= 1  # güzel


# ── daily stats integration ───────────────────────────────────────────


class TestDailyStats:
    def test_daily_sentiment_counts(self, tmp_db: Database):
        bid = tmp_db.add_brand("StatsBrand", ["stats"])
        sid = tmp_db.add_snapshot(bid, "autocomplete", "stats", [])

        tmp_db.upsert_suggestion(sid, bid, "stats kötü", 1, "negative", -0.6)
        tmp_db.upsert_suggestion(sid, bid, "stats iyi", 2, "positive", 0.6)
        tmp_db.upsert_suggestion(sid, bid, "stats nedir", 3, "neutral", 0.0)

        daily = tmp_db.get_daily_sentiment_counts(bid, days=7)
        assert len(daily) >= 1

        today = daily[-1]
        assert today["total"] >= 3

    def test_brand_stats(self, tmp_db: Database):
        bid = tmp_db.add_brand("BrandStats", ["bstats"])
        sid = tmp_db.add_snapshot(bid, "autocomplete", "bstats", [])

        tmp_db.upsert_suggestion(sid, bid, "bstats kötü", 1, "negative", -0.6)
        tmp_db.upsert_suggestion(sid, bid, "bstats iyi", 2, "positive", 0.6)

        stats = tmp_db.get_brand_stats(bid)
        assert stats is not None
        assert stats["total_suggestions"] == 2
        assert stats["negative_count"] == 1
        assert stats["positive_count"] == 1
