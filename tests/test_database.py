"""Tests for suggestguard.database module."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from suggestguard.database import Database


@pytest.fixture
def db():
    """In-memory database that auto-closes after each test."""
    database = Database(":memory:")
    database.connect()
    yield database
    database.close()


# ── Brand CRUD ───────────────────────────────────────────────────────


class TestBrands:
    def test_add_brand(self, db: Database):
        brand_id = db.add_brand("TestMarka", ["test", "test marka"])
        assert brand_id == 1

    def test_get_brand(self, db: Database):
        brand_id = db.add_brand("TestMarka", ["test"])
        brand = db.get_brand(brand_id)
        assert brand is not None
        assert brand["name"] == "TestMarka"
        assert brand["language"] == "tr"
        assert brand["country"] == "TR"
        assert brand["active"] == 1

    def test_get_brand_not_found(self, db: Database):
        assert db.get_brand(999) is None

    def test_get_brand_by_name(self, db: Database):
        db.add_brand("TestMarka", ["test"])
        brand = db.get_brand_by_name("TestMarka")
        assert brand is not None
        assert brand["name"] == "TestMarka"

    def test_get_brand_by_name_not_found(self, db: Database):
        assert db.get_brand_by_name("nonexistent") is None

    def test_list_brands_active_only(self, db: Database):
        db.add_brand("Active", ["a"])
        bid = db.add_brand("Inactive", ["i"])
        db.deactivate_brand(bid)

        active = db.list_brands(active_only=True)
        assert len(active) == 1
        assert active[0]["name"] == "Active"

    def test_list_brands_all(self, db: Database):
        db.add_brand("A", ["a"])
        bid = db.add_brand("B", ["b"])
        db.deactivate_brand(bid)

        all_brands = db.list_brands(active_only=False)
        assert len(all_brands) == 2

    def test_update_brand(self, db: Database):
        bid = db.add_brand("Old", ["old"])
        result = db.update_brand(bid, name="New", language="en")
        assert result is True
        brand = db.get_brand(bid)
        assert brand["name"] == "New"
        assert brand["language"] == "en"

    def test_update_brand_keywords_list(self, db: Database):
        bid = db.add_brand("Test", ["a"])
        db.update_brand(bid, keywords=["x", "y"])
        brand = db.get_brand(bid)
        assert '"x"' in brand["keywords"]

    def test_update_brand_no_kwargs(self, db: Database):
        bid = db.add_brand("Test", ["a"])
        assert db.update_brand(bid) is False

    def test_update_brand_invalid_field(self, db: Database):
        bid = db.add_brand("Test", ["a"])
        assert db.update_brand(bid, fake_field="nope") is False

    def test_update_brand_nonexistent(self, db: Database):
        assert db.update_brand(999, name="Ghost") is False

    def test_deactivate_brand(self, db: Database):
        bid = db.add_brand("Target", ["t"])
        result = db.deactivate_brand(bid)
        assert result is True
        brand = db.get_brand(bid)
        assert brand["active"] == 0


# ── Snapshots ────────────────────────────────────────────────────────


class TestSnapshots:
    def test_add_snapshot(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        sid = db.add_snapshot(bid, "autocomplete", "brand", ["sug1", "sug2"])
        assert sid == 1

    def test_get_latest_snapshot(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        db.add_snapshot(bid, "autocomplete", "brand q1", ["old"])
        db.add_snapshot(bid, "autocomplete", "brand q2", ["new"])
        latest = db.get_latest_snapshot(bid)
        assert latest is not None
        assert latest["query_used"] == "brand q2"

    def test_get_latest_snapshot_empty(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        assert db.get_latest_snapshot(bid) is None


# ── Suggestions ──────────────────────────────────────────────────────


class TestSuggestions:
    def _seed(self, db: Database) -> tuple[int, int]:
        """Create a brand + snapshot, return (brand_id, snapshot_id)."""
        bid = db.add_brand("Brand", ["brand"])
        sid = db.add_snapshot(bid, "autocomplete", "brand", [])
        return bid, sid

    def test_upsert_insert(self, db: Database):
        bid, sid = self._seed(db)
        sug_id = db.upsert_suggestion(sid, bid, "brand şikayet", 1, "negative", -0.8, "complaint")
        assert sug_id == 1

        rows = db.get_suggestions_for_brand(bid)
        assert len(rows) == 1
        assert rows[0]["text"] == "brand şikayet"
        assert rows[0]["times_seen"] == 1

    def test_upsert_update(self, db: Database):
        bid, sid = self._seed(db)
        db.upsert_suggestion(sid, bid, "brand şikayet", 1, "negative", -0.8)
        sid2 = db.add_snapshot(bid, "autocomplete", "brand", [])
        sug_id = db.upsert_suggestion(sid2, bid, "brand şikayet", 2, "negative", -0.9)

        rows = db.get_suggestions_for_brand(bid)
        assert len(rows) == 1
        assert rows[0]["times_seen"] == 2
        assert rows[0]["position"] == 2
        assert rows[0]["sentiment_score"] == -0.9
        assert rows[0]["id"] == sug_id

    def test_get_suggestions_filter_sentiment(self, db: Database):
        bid, sid = self._seed(db)
        db.upsert_suggestion(sid, bid, "good", 1, "positive", 0.9)
        db.upsert_suggestion(sid, bid, "bad", 2, "negative", -0.8)
        db.upsert_suggestion(sid, bid, "ok", 3, "neutral", 0.0)

        negatives = db.get_suggestions_for_brand(bid, sentiment="negative")
        assert len(negatives) == 1
        assert negatives[0]["text"] == "bad"

    def test_get_suggestions_filter_days(self, db: Database):
        bid, sid = self._seed(db)
        db.upsert_suggestion(sid, bid, "recent", 1, "neutral", 0.0)

        # Manually backdate one suggestion
        old_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        db.conn.execute(
            "INSERT INTO suggestions"
            " (snapshot_id, brand_id, text, position, sentiment, first_seen, last_seen)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, bid, "old", 2, "neutral", old_date, old_date),
        )
        db.conn.commit()

        recent = db.get_suggestions_for_brand(bid, days=7)
        assert len(recent) == 1
        assert recent[0]["text"] == "recent"

    def test_get_suggestion_history(self, db: Database):
        bid, sid = self._seed(db)
        db.upsert_suggestion(sid, bid, "brand", 1, "neutral", 0.0)
        history = db.get_suggestion_history(bid, "brand")
        assert len(history) == 1
        assert "snapshot_taken_at" in history[0]

    def test_get_new_suggestions(self, db: Database):
        bid, sid = self._seed(db)
        db.upsert_suggestion(sid, bid, "new sug", 1, "neutral", 0.0)

        old_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        db.conn.execute(
            "INSERT INTO suggestions"
            " (snapshot_id, brand_id, text, position, sentiment, first_seen, last_seen)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, bid, "old sug", 2, "neutral", old_date, old_date),
        )
        db.conn.commit()

        new = db.get_new_suggestions(bid, since_days=7)
        assert len(new) == 1
        assert new[0]["text"] == "new sug"

    def test_get_disappeared_suggestions(self, db: Database):
        bid, sid = self._seed(db)
        old_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        db.conn.execute(
            "INSERT INTO suggestions"
            " (snapshot_id, brand_id, text, position, sentiment, first_seen, last_seen)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, bid, "gone", 1, "negative", old_date, old_date),
        )
        db.conn.commit()
        db.upsert_suggestion(sid, bid, "still here", 2, "neutral", 0.0)

        gone = db.get_disappeared_suggestions(bid, not_seen_days=7)
        assert len(gone) == 1
        assert gone[0]["text"] == "gone"

    def test_get_daily_sentiment_counts(self, db: Database):
        bid, sid = self._seed(db)
        today = datetime.now().strftime("%Y-%m-%d")

        db.upsert_suggestion(sid, bid, "neg1", 1, "negative", -0.8)
        db.upsert_suggestion(sid, bid, "neg2", 2, "negative", -0.5)
        db.upsert_suggestion(sid, bid, "pos1", 3, "positive", 0.7)
        db.upsert_suggestion(sid, bid, "neu1", 4, "neutral", 0.0)

        counts = db.get_daily_sentiment_counts(bid, days=1)
        assert len(counts) == 1
        row = counts[0]
        assert row["date"] == today
        assert row["negative"] == 2
        assert row["positive"] == 1
        assert row["neutral"] == 1
        assert row["total"] == 4

    def test_get_top_negative_suggestions(self, db: Database):
        bid, sid = self._seed(db)
        db.upsert_suggestion(sid, bid, "bad1", 1, "negative", -0.9)
        db.upsert_suggestion(sid, bid, "bad2", 2, "negative", -0.5)
        db.upsert_suggestion(sid, bid, "good", 3, "positive", 0.9)

        # Upsert bad1 again to increase times_seen
        sid2 = db.add_snapshot(bid, "autocomplete", "brand", [])
        db.upsert_suggestion(sid2, bid, "bad1", 1, "negative", -0.9)

        top = db.get_top_negative_suggestions(bid, limit=10)
        assert len(top) == 2
        assert top[0]["text"] == "bad1"
        assert top[0]["times_seen"] == 2


# ── Campaigns ────────────────────────────────────────────────────────


class TestCampaigns:
    def test_add_campaign(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        cid = db.add_campaign(bid, "SEO Push", notes="Q1 campaign")
        assert cid == 1

    def test_end_campaign(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        cid = db.add_campaign(bid, "Campaign1")
        result = db.end_campaign(cid)
        assert result is True

        campaigns = db.list_campaigns(bid)
        assert campaigns[0]["ended_at"] is not None

    def test_end_campaign_already_ended(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        cid = db.add_campaign(bid, "C")
        db.end_campaign(cid)
        assert db.end_campaign(cid) is False

    def test_list_campaigns_by_brand(self, db: Database):
        b1 = db.add_brand("A", ["a"])
        b2 = db.add_brand("B", ["b"])
        db.add_campaign(b1, "C1")
        db.add_campaign(b2, "C2")

        assert len(db.list_campaigns(b1)) == 1
        assert len(db.list_campaigns(b2)) == 1

    def test_list_campaigns_all(self, db: Database):
        b1 = db.add_brand("A", ["a"])
        b2 = db.add_brand("B", ["b"])
        db.add_campaign(b1, "C1")
        db.add_campaign(b2, "C2")
        assert len(db.list_campaigns()) == 2

    def test_get_campaign_comparison(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        sid = db.add_snapshot(bid, "autocomplete", "brand", [])

        # Insert a suggestion BEFORE campaign
        old_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        db.conn.execute(
            "INSERT INTO suggestions"
            " (snapshot_id, brand_id, text, position, sentiment, first_seen, last_seen)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, bid, "old neg", 1, "negative", old_date, old_date),
        )
        db.conn.commit()

        cid = db.add_campaign(bid, "Push")

        # Insert a suggestion DURING campaign
        db.upsert_suggestion(sid, bid, "new pos", 2, "positive", 0.8)

        comparison = db.get_campaign_comparison(cid)
        assert comparison["before"]["negative"] == 1
        assert comparison["before"]["total"] == 1
        assert comparison["during"]["positive"] == 1
        assert comparison["during"]["total"] == 1

    def test_get_campaign_comparison_nonexistent(self, db: Database):
        assert db.get_campaign_comparison(999) == {}


# ── Stats ────────────────────────────────────────────────────────────


class TestStats:
    def test_get_brand_stats(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        sid = db.add_snapshot(bid, "autocomplete", "brand", [])

        db.upsert_suggestion(sid, bid, "neg1", 1, "negative", -0.9)
        db.upsert_suggestion(sid, bid, "neg2", 2, "negative", -0.5)
        db.upsert_suggestion(sid, bid, "pos1", 3, "positive", 0.7)
        db.upsert_suggestion(sid, bid, "neu1", 4, "neutral", 0.0)

        stats = db.get_brand_stats(bid)
        assert stats["total_suggestions"] == 4
        assert stats["negative_count"] == 2
        assert stats["positive_count"] == 1
        assert stats["neutral_count"] == 1
        assert stats["negative_ratio"] == 0.5
        assert stats["last_scan"] is not None
        assert stats["total_scans"] == 1
        assert stats["new_last_7d"] == 4
        assert stats["disappeared_last_7d"] == 0

    def test_get_brand_stats_empty(self, db: Database):
        bid = db.add_brand("Empty", ["e"])
        stats = db.get_brand_stats(bid)
        assert stats["total_suggestions"] == 0
        assert stats["negative_ratio"] == 0.0
        assert stats["last_scan"] is None
        assert stats["total_scans"] == 0

    def test_get_brand_stats_disappeared(self, db: Database):
        bid = db.add_brand("Brand", ["b"])
        sid = db.add_snapshot(bid, "autocomplete", "brand", [])

        old_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        db.conn.execute(
            "INSERT INTO suggestions"
            " (snapshot_id, brand_id, text, position, sentiment, first_seen, last_seen)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, bid, "vanished", 1, "negative", old_date, old_date),
        )
        db.conn.commit()

        stats = db.get_brand_stats(bid)
        assert stats["disappeared_last_7d"] == 1


# ── Context manager ──────────────────────────────────────────────────


class TestContextManager:
    def test_context_manager(self):
        with Database(":memory:") as db:
            bid = db.add_brand("CtxBrand", ["ctx"])
            assert bid == 1
            assert db.conn is not None
        assert db.conn is None


# ── Table creation ───────────────────────────────────────────────────


class TestSchema:
    def test_tables_exist(self, db: Database):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {t["name"] for t in tables}
        assert {"brands", "snapshots", "suggestions", "campaigns", "alerts"} <= names

    def test_indexes_exist(self, db: Database):
        indexes = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()
        names = {i["name"] for i in indexes}
        assert "idx_suggestions_brand_text" in names
        assert "idx_suggestions_sentiment" in names
        assert "idx_suggestions_last_seen" in names

    def test_foreign_keys_enabled(self, db: Database):
        row = db.conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1
