"""Diff engine for detecting changes between autocomplete suggestion snapshots."""

from __future__ import annotations

from suggestguard.database import Database


class DiffAnalyzer:
    """Compare snapshots and detect suggestion trends over time."""

    # ── snapshot comparison ──────────────────────────────────────────

    @staticmethod
    def compare_snapshots(
        previous: list[dict],
        current: list[dict],
    ) -> dict:
        """Compare two suggestion lists and return a change report.

        Each item in *previous* / *current* must have at least a
        ``"text"`` key.  An optional ``"position"`` key enables
        position-change tracking.

        Returns::

            {
                "new_suggestions":   [dict, ...],
                "disappeared":       [dict, ...],
                "position_changes":  [{"text", "old_position", "new_position"}, ...],
                "unchanged":         [dict, ...],
                "summary": {
                    "new_count": int,
                    "disappeared_count": int,
                    "position_change_count": int,
                    "unchanged_count": int,
                    "total_previous": int,
                    "total_current": int,
                },
            }
        """
        prev_map: dict[str, dict] = {s["text"]: s for s in previous}
        curr_map: dict[str, dict] = {s["text"]: s for s in current}

        prev_texts = set(prev_map)
        curr_texts = set(curr_map)

        new_texts = curr_texts - prev_texts
        gone_texts = prev_texts - curr_texts
        common_texts = prev_texts & curr_texts

        new_suggestions = [s for s in current if s["text"] in new_texts]
        disappeared = [s for s in previous if s["text"] in gone_texts]

        position_changes: list[dict] = []
        unchanged: list[dict] = []

        for s in current:
            text = s["text"]
            if text not in common_texts:
                continue
            old_pos = prev_map[text].get("position")
            new_pos = s.get("position")
            if old_pos is not None and new_pos is not None and old_pos != new_pos:
                position_changes.append(
                    {
                        "text": text,
                        "old_position": old_pos,
                        "new_position": new_pos,
                    }
                )
            else:
                unchanged.append(s)

        return {
            "new_suggestions": new_suggestions,
            "disappeared": disappeared,
            "position_changes": position_changes,
            "unchanged": unchanged,
            "summary": {
                "new_count": len(new_suggestions),
                "disappeared_count": len(disappeared),
                "position_change_count": len(position_changes),
                "unchanged_count": len(unchanged),
                "total_previous": len(previous),
                "total_current": len(current),
            },
        }

    # ── trend detection ──────────────────────────────────────────────

    @staticmethod
    def detect_trends(brand_id: int, db: Database, days: int = 30) -> dict:
        """Analyse suggestion trends for *brand_id* over the last *days*.

        Returns::

            {
                "rising_negative":     [dict, ...],  # new negative in last 7 d
                "declining_negative":  [dict, ...],  # negative disappeared last 7 d
                "persistent_negative": [dict, ...],  # negative seen > 3 times
                "negative_ratio_trend": [
                    {"date": str, "ratio": float}, ...
                ],
            }
        """
        rising = db.get_new_suggestions(brand_id, since_days=7)
        rising_negative = [s for s in rising if s.get("sentiment") == "negative"]

        disappeared = db.get_disappeared_suggestions(brand_id, not_seen_days=7)
        declining_negative = [s for s in disappeared if s.get("sentiment") == "negative"]

        all_suggestions = db.get_suggestions_for_brand(brand_id, sentiment="negative")
        persistent_negative = [s for s in all_suggestions if (s.get("times_seen") or 0) >= 3]

        daily = db.get_daily_sentiment_counts(brand_id, days=days)
        negative_ratio_trend = []
        for row in daily:
            total = row["total"]
            ratio = round(row["negative"] / total, 4) if total > 0 else 0.0
            negative_ratio_trend.append({"date": row["date"], "ratio": ratio})

        return {
            "rising_negative": rising_negative,
            "declining_negative": declining_negative,
            "persistent_negative": persistent_negative,
            "negative_ratio_trend": negative_ratio_trend,
        }
