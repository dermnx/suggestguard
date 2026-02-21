"""Generate demo data for testing the Streamlit dashboard."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta

from suggestguard.database import Database

# ── suggestion pools ─────────────────────────────────────────────────

_NEGATIVE_SUGGESTIONS = [
    ("demo marka dolandırıcı", "negative", -0.9, "fraud"),
    ("demo marka sahte", "negative", -0.9, "fraud"),
    ("demo marka şikayet", "negative", -0.6, "complaint"),
    ("demo marka sorun", "negative", -0.6, "complaint"),
    ("demo marka berbat", "negative", -0.6, "quality"),
    ("demo marka kötü", "negative", -0.6, "quality"),
    ("demo marka dava", "negative", -0.3, "legal"),
    ("demo marka güvenilir mi", "negative", -0.3, "trust"),
    ("demo marka kapandı mı", "negative", -0.3, "trust"),
    ("demo marka iade", "negative", -0.3, "refund"),
]

_POSITIVE_SUGGESTIONS = [
    ("demo marka en iyi", "positive", 0.6, None),
    ("demo marka tavsiye", "positive", 0.6, None),
    ("demo marka güvenilir", "positive", 0.6, None),
    ("demo marka kaliteli", "positive", 0.6, None),
    ("demo marka indirim", "positive", 0.6, None),
    ("demo marka kampanya", "positive", 0.6, None),
    ("demo marka harika", "positive", 0.6, None),
]

_NEUTRAL_SUGGESTIONS = [
    ("demo marka nedir", "neutral", 0.0, None),
    ("demo marka iletişim", "neutral", 0.0, None),
    ("demo marka adres", "neutral", 0.0, None),
    ("demo marka çalışma saatleri", "neutral", 0.0, None),
    ("demo marka telefon", "neutral", 0.0, None),
    ("demo marka bayilik", "neutral", 0.0, None),
    ("demo marka fiyat", "neutral", 0.0, None),
    ("demo marka şube", "neutral", 0.0, None),
]

_ALL_SUGGESTIONS = _NEGATIVE_SUGGESTIONS + _POSITIVE_SUGGESTIONS + _NEUTRAL_SUGGESTIONS

DEMO_BRAND_NAME = "Demo Marka"


# ── public API ───────────────────────────────────────────────────────


def seed_demo_data(db: Database, days: int = 30) -> int:
    """Populate *db* with a demo brand and *days* of fake scan data.

    Returns the brand id of the created (or existing) demo brand.

    Generates:
    - 1 brand ("Demo Marka")
    - 1 snapshot per day for *days* days
    - Random suggestions per snapshot (with slight daily variation)
    """
    # ── ensure brand exists ──────────────────────────────────────
    existing = db.get_brand_by_name(DEMO_BRAND_NAME)
    if existing:
        return existing["id"]

    brand_id = db.add_brand(
        name=DEMO_BRAND_NAME,
        keywords=["demo marka"],
        language="tr",
        country="TR",
    )

    rng = random.Random(42)  # deterministic for reproducibility
    now = datetime.now()

    for day_offset in range(days, 0, -1):
        day = now - timedelta(days=day_offset)
        day_str = day.strftime("%Y-%m-%d %H:%M:%S")

        # pick a random subset of suggestions for this day
        sample_size = rng.randint(12, len(_ALL_SUGGESTIONS))
        day_suggestions = rng.sample(_ALL_SUGGESTIONS, sample_size)

        # create snapshot
        snapshot_id = _add_snapshot_at(
            db,
            brand_id,
            day_str,
            [s[0] for s in day_suggestions],
        )

        # insert suggestions
        for i, (text, sentiment, score, category) in enumerate(day_suggestions):
            # vary times_seen to create a more realistic pattern
            times_seen = rng.randint(1, day_offset // 3 + 1)
            first_seen = (day - timedelta(days=rng.randint(0, min(day_offset, 14)))).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            _upsert_suggestion_at(
                db,
                snapshot_id=snapshot_id,
                brand_id=brand_id,
                text=text,
                position=i + 1,
                sentiment=sentiment,
                sentiment_score=score,
                category=category,
                first_seen=first_seen,
                last_seen=day_str,
                times_seen=times_seen,
            )

    # ── add sample campaigns ─────────────────────────────────────
    _seed_demo_campaigns(db, brand_id, now, days)

    return brand_id


# ── campaign seeder ──────────────────────────────────────────────────


def _seed_demo_campaigns(db: Database, brand_id: int, now: datetime, days: int) -> None:
    """Add two sample campaigns to the demo brand.

    1. A completed campaign (ended 10 days ago, started 20 days ago)
    2. An active campaign (started 5 days ago, still running)
    """
    # Campaign 1 — completed
    started_1 = (now - timedelta(days=min(20, days - 1))).strftime("%Y-%m-%d %H:%M:%S")
    ended_1 = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    db.conn.execute(
        "INSERT INTO campaigns (brand_id, name, started_at, ended_at, notes)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            brand_id,
            "SEO İyileştirme Kampanyası",
            started_1,
            ended_1,
            "Negatif içeriklere karşı SEO çalışması yapıldı.",
        ),
    )
    db.conn.commit()

    # Campaign 2 — active
    started_2 = (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    db.conn.execute(
        "INSERT INTO campaigns (brand_id, name, started_at, ended_at, notes)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            brand_id,
            "İçerik Pazarlama Kampanyası",
            started_2,
            None,
            "Pozitif içerik üretimi ile itibar yönetimi.",
        ),
    )
    db.conn.commit()


# ── internal helpers ─────────────────────────────────────────────────


def _add_snapshot_at(db: Database, brand_id: int, taken_at: str, queries: list[str]) -> int:
    """Insert a snapshot with a specific timestamp."""
    cur = db.conn.execute(
        """INSERT INTO snapshots (brand_id, source, taken_at, query_used, raw_data)
           VALUES (?, ?, ?, ?, ?)""",
        (
            brand_id,
            "autocomplete",
            taken_at,
            json.dumps(queries, ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
        ),
    )
    db.conn.commit()
    return cur.lastrowid


def _upsert_suggestion_at(
    db: Database,
    *,
    snapshot_id: int,
    brand_id: int,
    text: str,
    position: int,
    sentiment: str,
    sentiment_score: float,
    category: str | None,
    first_seen: str,
    last_seen: str,
    times_seen: int,
) -> int:
    """Insert or update a suggestion with explicit timestamps."""
    existing = db.conn.execute(
        "SELECT id FROM suggestions WHERE brand_id = ? AND text = ?",
        (brand_id, text),
    ).fetchone()

    if existing:
        db.conn.execute(
            """UPDATE suggestions
               SET snapshot_id = ?, position = ?, sentiment = ?,
                   sentiment_score = ?, category = ?,
                   last_seen = ?, times_seen = times_seen + 1
               WHERE id = ?""",
            (
                snapshot_id,
                position,
                sentiment,
                sentiment_score,
                category,
                last_seen,
                existing["id"],
            ),
        )
        db.conn.commit()
        return existing["id"]

    cur = db.conn.execute(
        """INSERT INTO suggestions
           (snapshot_id, brand_id, text, position, sentiment, sentiment_score,
            category, first_seen, last_seen, times_seen)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            snapshot_id,
            brand_id,
            text,
            position,
            sentiment,
            sentiment_score,
            category,
            first_seen,
            last_seen,
            times_seen,
        ),
    )
    db.conn.commit()
    return cur.lastrowid
