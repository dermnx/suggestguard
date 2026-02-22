"""Database layer for storing and querying autocomplete suggestion data."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for SuggestGuard."""

    def __init__(self, db_path: str = "suggestguard.db") -> None:
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    # ── Context manager ──────────────────────────────────────────────

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ── Connection management ────────────────────────────────────────

    def connect(self) -> None:
        """Open database connection and initialise schema."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ── Schema ───────────────────────────────────────────────────────

    def _init_tables(self) -> None:
        try:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS brands (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL UNIQUE,
                keywords        TEXT NOT NULL,
                language        TEXT DEFAULT 'tr',
                country         TEXT DEFAULT 'TR',
                expand_az       BOOLEAN DEFAULT 1,
                expand_turkish  BOOLEAN DEFAULT 1,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                active          BOOLEAN DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_id    INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
                source      TEXT NOT NULL,
                taken_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                query_used  TEXT NOT NULL,
                raw_data    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS suggestions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
                brand_id        INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
                text            TEXT NOT NULL,
                position        INTEGER,
                sentiment       TEXT,
                sentiment_score REAL,
                category        TEXT,
                first_seen      DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen       DATETIME DEFAULT CURRENT_TIMESTAMP,
                times_seen      INTEGER DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_suggestions_brand_text
                ON suggestions(brand_id, text);
            CREATE INDEX IF NOT EXISTS idx_suggestions_sentiment
                ON suggestions(brand_id, sentiment);
            CREATE INDEX IF NOT EXISTS idx_suggestions_last_seen
                ON suggestions(brand_id, last_seen);

            CREATE TABLE IF NOT EXISTS campaigns (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_id    INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                started_at  DATETIME NOT NULL,
                ended_at    DATETIME,
                notes       TEXT
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_id   INTEGER REFERENCES suggestions(id),
                alert_type      TEXT NOT NULL,
                channel         TEXT NOT NULL,
                sent_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
                message         TEXT NOT NULL
            );
        """)
        except sqlite3.Error:
            logger.exception("Failed to initialise database schema")

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return dict(row)

    def _rows_to_dicts(self, rows: list[sqlite3.Row]) -> list[dict]:
        return [dict(r) for r in rows]

    # ── Brands ───────────────────────────────────────────────────────

    def add_brand(
        self,
        name: str,
        keywords: list[str],
        language: str = "tr",
        country: str = "TR",
        expand_az: bool = True,
        expand_turkish: bool = True,
    ) -> int:
        """Add a new brand and return its ID.

        Raises ``ValueError`` if a brand with the same name already exists.
        """
        try:
            cur = self.conn.execute(
                """INSERT INTO brands
                   (name, keywords, language, country, expand_az, expand_turkish, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    json.dumps(keywords, ensure_ascii=False),
                    language,
                    country,
                    expand_az,
                    expand_turkish,
                    self._now(),
                ),
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Brand with name '{name}' already exists") from None

    def get_brand(self, brand_id: int) -> dict | None:
        """Return brand by ID, or ``None`` if not found."""
        row = self.conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
        return self._row_to_dict(row)

    def get_brand_by_name(self, name: str) -> dict | None:
        """Return brand by name, or ``None`` if not found."""
        row = self.conn.execute("SELECT * FROM brands WHERE name = ?", (name,)).fetchone()
        return self._row_to_dict(row)

    def list_brands(self, active_only: bool = True) -> list[dict]:
        """Return all brands, optionally filtered to active ones."""
        if active_only:
            rows = self.conn.execute("SELECT * FROM brands WHERE active = 1").fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM brands").fetchall()
        return self._rows_to_dicts(rows)

    def update_brand(self, brand_id: int, **kwargs) -> bool:
        """Update allowed brand fields. Return ``True`` if a row was changed."""
        if not kwargs:
            return False
        allowed = {
            "name",
            "keywords",
            "language",
            "country",
            "expand_az",
            "expand_turkish",
            "active",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        if "keywords" in fields and isinstance(fields["keywords"], list):
            fields["keywords"] = json.dumps(fields["keywords"], ensure_ascii=False)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [brand_id]
        cur = self.conn.execute(
            f"UPDATE brands SET {set_clause} WHERE id = ?",
            values,  # noqa: S608
        )
        self.conn.commit()
        return cur.rowcount > 0

    def deactivate_brand(self, brand_id: int) -> bool:
        """Mark a brand as inactive."""
        return self.update_brand(brand_id, active=False)

    # ── Snapshots ────────────────────────────────────────────────────

    def add_snapshot(
        self, brand_id: int, source: str, query_used: str, raw_data: list | dict
    ) -> int:
        """Save a scan snapshot and return its ID."""
        cur = self.conn.execute(
            """INSERT INTO snapshots (brand_id, source, taken_at, query_used, raw_data)
               VALUES (?, ?, ?, ?, ?)""",
            (brand_id, source, self._now(), query_used, json.dumps(raw_data, ensure_ascii=False)),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_latest_snapshot(self, brand_id: int) -> dict | None:
        """Return the most recent snapshot for a brand."""
        row = self.conn.execute(
            "SELECT * FROM snapshots WHERE brand_id = ? ORDER BY id DESC LIMIT 1",
            (brand_id,),
        ).fetchone()
        return self._row_to_dict(row)

    # ── Suggestions ──────────────────────────────────────────────────

    def upsert_suggestion(
        self,
        snapshot_id: int,
        brand_id: int,
        text: str,
        position: int | None = None,
        sentiment: str | None = None,
        sentiment_score: float | None = None,
        category: str | None = None,
    ) -> int:
        """Insert or update a suggestion, incrementing *times_seen* on update."""
        try:
            existing = self.conn.execute(
                "SELECT id, times_seen FROM suggestions WHERE brand_id = ? AND text = ?",
                (brand_id, text),
            ).fetchone()

            now = self._now()

            if existing:
                self.conn.execute(
                    """UPDATE suggestions
                       SET snapshot_id = ?, position = ?, sentiment = ?,
                           sentiment_score = ?, category = ?,
                           last_seen = ?, times_seen = ?
                       WHERE id = ?""",
                    (
                        snapshot_id,
                        position,
                        sentiment,
                        sentiment_score,
                        category,
                        now,
                        existing["times_seen"] + 1,
                        existing["id"],
                    ),
                )
                self.conn.commit()
                return existing["id"]

            cur = self.conn.execute(
                """INSERT INTO suggestions
                   (snapshot_id, brand_id, text, position, sentiment, sentiment_score,
                    category, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    brand_id,
                    text,
                    position,
                    sentiment,
                    sentiment_score,
                    category,
                    now,
                    now,
                ),
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def get_suggestions_for_brand(
        self,
        brand_id: int,
        days: int | None = None,
        sentiment: str | None = None,
    ) -> list[dict]:
        """Return suggestions for a brand, optionally filtered by recency or sentiment."""
        query = "SELECT * FROM suggestions WHERE brand_id = ?"
        params: list = [brand_id]

        if days is not None:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            query += " AND last_seen >= ?"
            params.append(cutoff)

        if sentiment is not None:
            query += " AND sentiment = ?"
            params.append(sentiment)

        query += " ORDER BY last_seen DESC"
        return self._rows_to_dicts(self.conn.execute(query, params).fetchall())

    def get_suggestion_history(self, brand_id: int, text: str) -> list[dict]:
        """Return snapshot history for a specific suggestion text."""
        rows = self.conn.execute(
            """SELECT s.*, snap.taken_at AS snapshot_taken_at, snap.query_used
               FROM suggestions s
               JOIN snapshots snap ON s.snapshot_id = snap.id
               WHERE s.brand_id = ? AND s.text = ?
               ORDER BY snap.taken_at""",
            (brand_id, text),
        ).fetchall()
        return self._rows_to_dicts(rows)

    def get_new_suggestions(self, brand_id: int, since_days: int = 7) -> list[dict]:
        """Return suggestions first seen within the last *since_days*."""
        cutoff = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self.conn.execute(
            """SELECT * FROM suggestions
               WHERE brand_id = ? AND first_seen >= ?
               ORDER BY first_seen DESC""",
            (brand_id, cutoff),
        ).fetchall()
        return self._rows_to_dicts(rows)

    def get_disappeared_suggestions(self, brand_id: int, not_seen_days: int = 7) -> list[dict]:
        """Return suggestions not seen for at least *not_seen_days*."""
        cutoff = (datetime.now() - timedelta(days=not_seen_days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self.conn.execute(
            """SELECT * FROM suggestions
               WHERE brand_id = ? AND last_seen < ?
               ORDER BY last_seen DESC""",
            (brand_id, cutoff),
        ).fetchall()
        return self._rows_to_dicts(rows)

    def get_daily_sentiment_counts(self, brand_id: int, days: int = 30) -> list[dict]:
        """Return per-day sentiment counts for the last *days* days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            """SELECT
                   DATE(first_seen) AS date,
                   SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS negative,
                   SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN sentiment = 'neutral'  THEN 1 ELSE 0 END) AS neutral,
                   COUNT(*) AS total
               FROM suggestions
               WHERE brand_id = ? AND DATE(first_seen) >= ?
               GROUP BY DATE(first_seen)
               ORDER BY DATE(first_seen)""",
            (brand_id, cutoff),
        ).fetchall()
        return self._rows_to_dicts(rows)

    def get_top_negative_suggestions(self, brand_id: int, limit: int = 10) -> list[dict]:
        """Return the most frequently seen negative suggestions."""
        rows = self.conn.execute(
            """SELECT * FROM suggestions
               WHERE brand_id = ? AND sentiment = 'negative'
               ORDER BY times_seen DESC, last_seen DESC
               LIMIT ?""",
            (brand_id, limit),
        ).fetchall()
        return self._rows_to_dicts(rows)

    # ── Campaigns ────────────────────────────────────────────────────

    def add_campaign(self, brand_id: int, name: str, notes: str | None = None) -> int:
        """Create a new campaign and return its ID."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.execute(
            "INSERT INTO campaigns (brand_id, name, started_at, notes) VALUES (?, ?, ?, ?)",
            (brand_id, name, now, notes),
        )
        self.conn.commit()
        return cur.lastrowid

    def end_campaign(self, campaign_id: int) -> bool:
        """Mark a campaign as ended. Return ``True`` if updated."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.execute(
            "UPDATE campaigns SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
            (now, campaign_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_campaigns(self, brand_id: int | None = None) -> list[dict]:
        """Return campaigns, optionally filtered by brand."""
        if brand_id is not None:
            rows = self.conn.execute(
                "SELECT * FROM campaigns WHERE brand_id = ? ORDER BY started_at DESC",
                (brand_id,),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM campaigns ORDER BY started_at DESC").fetchall()
        return self._rows_to_dicts(rows)

    def get_campaign_comparison(self, campaign_id: int) -> dict:
        """Return before/during sentiment counts for a campaign."""
        campaign = self.conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if campaign is None:
            return {}

        brand_id = campaign["brand_id"]
        started_at = campaign["started_at"]
        ended_at = campaign["ended_at"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        before = self.conn.execute(
            """SELECT
                   SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS negative,
                   SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN sentiment = 'neutral'  THEN 1 ELSE 0 END) AS neutral,
                   COUNT(*) AS total
               FROM suggestions
               WHERE brand_id = ? AND first_seen < ?""",
            (brand_id, started_at),
        ).fetchone()

        during = self.conn.execute(
            """SELECT
                   SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS negative,
                   SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN sentiment = 'neutral'  THEN 1 ELSE 0 END) AS neutral,
                   COUNT(*) AS total
               FROM suggestions
               WHERE brand_id = ? AND first_seen >= ? AND first_seen <= ?""",
            (brand_id, started_at, ended_at),
        ).fetchone()

        return {
            "campaign": dict(campaign),
            "before": dict(before),
            "during": dict(during),
        }

    # ── Stats ────────────────────────────────────────────────────────

    def get_brand_stats(self, brand_id: int) -> dict:
        """Return aggregate statistics for a brand."""
        counts = self.conn.execute(
            """SELECT
                   COUNT(*) AS total_suggestions,
                   SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS negative_count,
                   SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS positive_count,
                   SUM(CASE WHEN sentiment = 'neutral'  THEN 1 ELSE 0 END) AS neutral_count
               FROM suggestions
               WHERE brand_id = ?""",
            (brand_id,),
        ).fetchone()

        total = counts["total_suggestions"] or 0
        negative = counts["negative_count"] or 0
        positive = counts["positive_count"] or 0
        neutral = counts["neutral_count"] or 0

        last_scan_row = self.conn.execute(
            "SELECT taken_at FROM snapshots WHERE brand_id = ? ORDER BY taken_at DESC LIMIT 1",
            (brand_id,),
        ).fetchone()

        total_scans = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM snapshots WHERE brand_id = ?", (brand_id,)
        ).fetchone()["cnt"]

        cutoff_7d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

        new_7d = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM suggestions WHERE brand_id = ? AND first_seen >= ?",
            (brand_id, cutoff_7d),
        ).fetchone()["cnt"]

        disappeared_7d = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM suggestions WHERE brand_id = ? AND last_seen < ?",
            (brand_id, cutoff_7d),
        ).fetchone()["cnt"]

        return {
            "total_suggestions": total,
            "negative_count": negative,
            "positive_count": positive,
            "neutral_count": neutral,
            "negative_ratio": round(negative / total, 4) if total > 0 else 0.0,
            "last_scan": last_scan_row["taken_at"] if last_scan_row else None,
            "total_scans": total_scans,
            "new_last_7d": new_7d,
            "disappeared_last_7d": disappeared_7d,
        }
