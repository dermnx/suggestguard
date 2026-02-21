"""Tests for suggestguard.analyzers.diff module."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from suggestguard.analyzers.diff import DiffAnalyzer
from suggestguard.database import Database


@pytest.fixture
def diff():
    return DiffAnalyzer()


# ── compare_snapshots ────────────────────────────────────────────────


class TestCompareSnapshots:
    def test_new_suggestions(self, diff: DiffAnalyzer):
        prev = [{"text": "brand a", "position": 1}]
        curr = [
            {"text": "brand a", "position": 1},
            {"text": "brand b", "position": 2},
        ]
        result = diff.compare_snapshots(prev, curr)
        assert len(result["new_suggestions"]) == 1
        assert result["new_suggestions"][0]["text"] == "brand b"
        assert result["summary"]["new_count"] == 1

    def test_disappeared_suggestions(self, diff: DiffAnalyzer):
        prev = [
            {"text": "brand a", "position": 1},
            {"text": "brand b", "position": 2},
        ]
        curr = [{"text": "brand a", "position": 1}]
        result = diff.compare_snapshots(prev, curr)
        assert len(result["disappeared"]) == 1
        assert result["disappeared"][0]["text"] == "brand b"
        assert result["summary"]["disappeared_count"] == 1

    def test_position_change(self, diff: DiffAnalyzer):
        prev = [
            {"text": "brand a", "position": 1},
            {"text": "brand b", "position": 2},
        ]
        curr = [
            {"text": "brand a", "position": 2},
            {"text": "brand b", "position": 1},
        ]
        result = diff.compare_snapshots(prev, curr)
        assert len(result["position_changes"]) == 2
        changes = {c["text"]: c for c in result["position_changes"]}
        assert changes["brand a"]["old_position"] == 1
        assert changes["brand a"]["new_position"] == 2
        assert changes["brand b"]["old_position"] == 2
        assert changes["brand b"]["new_position"] == 1

    def test_unchanged(self, diff: DiffAnalyzer):
        prev = [{"text": "brand a", "position": 1}]
        curr = [{"text": "brand a", "position": 1}]
        result = diff.compare_snapshots(prev, curr)
        assert len(result["unchanged"]) == 1
        assert result["unchanged"][0]["text"] == "brand a"
        assert result["summary"]["unchanged_count"] == 1

    def test_both_empty(self, diff: DiffAnalyzer):
        result = diff.compare_snapshots([], [])
        assert result["new_suggestions"] == []
        assert result["disappeared"] == []
        assert result["position_changes"] == []
        assert result["unchanged"] == []
        assert result["summary"]["total_previous"] == 0
        assert result["summary"]["total_current"] == 0

    def test_previous_empty(self, diff: DiffAnalyzer):
        curr = [{"text": "x", "position": 1}]
        result = diff.compare_snapshots([], curr)
        assert len(result["new_suggestions"]) == 1
        assert result["disappeared"] == []

    def test_current_empty(self, diff: DiffAnalyzer):
        prev = [{"text": "x", "position": 1}]
        result = diff.compare_snapshots(prev, [])
        assert result["new_suggestions"] == []
        assert len(result["disappeared"]) == 1

    def test_no_position_field_counts_as_unchanged(self, diff: DiffAnalyzer):
        prev = [{"text": "brand a"}]
        curr = [{"text": "brand a"}]
        result = diff.compare_snapshots(prev, curr)
        assert len(result["unchanged"]) == 1
        assert result["position_changes"] == []

    def test_mixed_changes(self, diff: DiffAnalyzer):
        prev = [
            {"text": "a", "position": 1},
            {"text": "b", "position": 2},
            {"text": "c", "position": 3},
        ]
        curr = [
            {"text": "a", "position": 1},  # unchanged
            {"text": "b", "position": 5},  # position change
            {"text": "d", "position": 2},  # new
        ]
        result = diff.compare_snapshots(prev, curr)
        assert result["summary"]["new_count"] == 1
        assert result["summary"]["disappeared_count"] == 1
        assert result["summary"]["position_change_count"] == 1
        assert result["summary"]["unchanged_count"] == 1

    def test_order_preserved_new(self, diff: DiffAnalyzer):
        curr = [
            {"text": "z", "position": 1},
            {"text": "a", "position": 2},
            {"text": "m", "position": 3},
        ]
        result = diff.compare_snapshots([], curr)
        texts = [s["text"] for s in result["new_suggestions"]]
        assert texts == ["z", "a", "m"]

    def test_summary_totals(self, diff: DiffAnalyzer):
        prev = [{"text": "a"}, {"text": "b"}]
        curr = [{"text": "b"}, {"text": "c"}, {"text": "d"}]
        result = diff.compare_snapshots(prev, curr)
        assert result["summary"]["total_previous"] == 2
        assert result["summary"]["total_current"] == 3


# ── detect_trends ────────────────────────────────────────────────────


@pytest.fixture
def db():
    database = Database(":memory:")
    database.connect()
    yield database
    database.close()


class TestDetectTrends:
    def _seed(self, db: Database):
        bid = db.add_brand("Brand", ["brand"])
        sid = db.add_snapshot(bid, "autocomplete", "brand", [])
        return bid, sid

    def test_rising_negative(self, db: Database):
        bid, sid = self._seed(db)
        # recent negative → should appear in rising
        db.upsert_suggestion(sid, bid, "brand scam", 1, "negative", -0.9)
        # recent neutral → should NOT appear
        db.upsert_suggestion(sid, bid, "brand info", 2, "neutral", 0.0)

        result = DiffAnalyzer.detect_trends(bid, db)
        assert len(result["rising_negative"]) == 1
        assert result["rising_negative"][0]["text"] == "brand scam"

    def test_declining_negative(self, db: Database):
        bid, sid = self._seed(db)
        old = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        db.conn.execute(
            "INSERT INTO suggestions"
            " (snapshot_id, brand_id, text, position, sentiment, first_seen, last_seen)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, bid, "brand fraud", 1, "negative", old, old),
        )
        db.conn.commit()

        result = DiffAnalyzer.detect_trends(bid, db)
        assert len(result["declining_negative"]) == 1
        assert result["declining_negative"][0]["text"] == "brand fraud"

    def test_persistent_negative(self, db: Database):
        bid, sid = self._seed(db)
        # upsert 3 times to get times_seen=3
        db.upsert_suggestion(sid, bid, "brand bad", 1, "negative", -0.6)
        sid2 = db.add_snapshot(bid, "autocomplete", "brand", [])
        db.upsert_suggestion(sid2, bid, "brand bad", 1, "negative", -0.6)
        sid3 = db.add_snapshot(bid, "autocomplete", "brand", [])
        db.upsert_suggestion(sid3, bid, "brand bad", 1, "negative", -0.6)

        result = DiffAnalyzer.detect_trends(bid, db)
        assert len(result["persistent_negative"]) == 1
        assert result["persistent_negative"][0]["text"] == "brand bad"

    def test_persistent_negative_below_threshold(self, db: Database):
        bid, sid = self._seed(db)
        db.upsert_suggestion(sid, bid, "brand bad", 1, "negative", -0.6)
        # only seen once → not persistent

        result = DiffAnalyzer.detect_trends(bid, db)
        assert result["persistent_negative"] == []

    def test_negative_ratio_trend(self, db: Database):
        bid, sid = self._seed(db)
        db.upsert_suggestion(sid, bid, "brand neg", 1, "negative", -0.8)
        db.upsert_suggestion(sid, bid, "brand pos", 2, "positive", 0.6)

        result = DiffAnalyzer.detect_trends(bid, db, days=1)
        trend = result["negative_ratio_trend"]
        assert len(trend) == 1
        assert trend[0]["ratio"] == 0.5

    def test_empty_brand(self, db: Database):
        bid, _sid = self._seed(db)
        result = DiffAnalyzer.detect_trends(bid, db)
        assert result["rising_negative"] == []
        assert result["declining_negative"] == []
        assert result["persistent_negative"] == []
        assert result["negative_ratio_trend"] == []
