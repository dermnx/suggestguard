"""Scan engine and CLI entry point for SuggestGuard."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Callable

from suggestguard.analyzers.diff import DiffAnalyzer
from suggestguard.analyzers.sentiment import SentimentAnalyzer
from suggestguard.analyzers.turkish import TurkishTextProcessor
from suggestguard.collectors.autocomplete import AutocompleteCollector
from suggestguard.config import SuggestGuardConfig, get_db
from suggestguard.database import Database
from suggestguard.notifiers import get_notifiers

logger = logging.getLogger(__name__)


class ScanEngine:
    """Orchestrates brand scanning: collect → analyse → store → diff → notify."""

    def __init__(self, db: Database, config: SuggestGuardConfig) -> None:
        self.db = db
        self.config = config
        self._sentiment = SentimentAnalyzer()
        self._tp = TurkishTextProcessor()
        self._collector: AutocompleteCollector | None = None

    # ── lifecycle ─────────────────────────────────────────────────────

    def _get_collector(self) -> AutocompleteCollector:
        if self._collector is None:
            self._collector = AutocompleteCollector(
                request_delay=self.config.get("settings.request_delay", 1.5),
                max_workers=self.config.get("settings.max_workers", 3),
                user_agent=self.config.get(
                    "settings.user_agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                ),
            )
        return self._collector

    async def close(self) -> None:
        if self._collector is not None:
            await self._collector.close()
            self._collector = None

    # ── single brand scan ─────────────────────────────────────────────

    async def scan_brand(
        self,
        brand: dict,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        """Run a full scan for one brand.

        Steps:
            1. Collect autocomplete suggestions
            2. Deduplicate suggestion texts
            3. Run sentiment analysis on each unique text
            4. Save snapshot + suggestions to DB
            5. Compare with previous snapshot (diff)
            6. Send notifications for new negatives

        Returns a scan report dict.
        """
        brand_id = brand["id"]
        brand_name = brand["name"]
        language = brand.get("language", "tr")

        collector = self._get_collector()

        # 1. Collect
        raw_results = await collector.collect_brand(brand, progress_callback)

        # 2. Deduplicate all suggestion texts across queries
        seen: set[str] = set()
        unique_suggestions: list[str] = []
        for result in raw_results:
            for text in result.get("suggestions", []):
                normalized = self._tp.normalize(text)
                if normalized not in seen:
                    seen.add(normalized)
                    unique_suggestions.append(text)

        # 3. Sentiment analysis
        analyses = self._sentiment.analyze_batch(unique_suggestions, brand_name, language)

        # 4. Get previous snapshot for diff
        prev_snapshot = self.db.get_latest_snapshot(brand_id)
        previous_suggestions: list[dict] = []
        if prev_snapshot:
            previous_suggestions = self.db.get_suggestions_for_brand(brand_id)

        # 5. Save snapshot + suggestions
        snapshot_id = self.db.add_snapshot(
            brand_id=brand_id,
            source="autocomplete",
            query_used=json.dumps([r["query"] for r in raw_results], ensure_ascii=False),
            raw_data=raw_results,
        )

        current_suggestions: list[dict] = []
        for i, text in enumerate(unique_suggestions):
            analysis = analyses[i]
            self.db.upsert_suggestion(
                snapshot_id=snapshot_id,
                brand_id=brand_id,
                text=text,
                position=i + 1,
                sentiment=analysis["sentiment"],
                sentiment_score=analysis["score"],
                category=analysis["category"],
            )
            current_suggestions.append(
                {
                    "text": text,
                    "position": i + 1,
                    "sentiment": analysis["sentiment"],
                    "score": analysis["score"],
                    "category": analysis["category"],
                }
            )

        # 6. Diff
        prev_for_diff = [
            {"text": s["text"], "position": s.get("position")} for s in previous_suggestions
        ]
        curr_for_diff = [
            {"text": s["text"], "position": s["position"]} for s in current_suggestions
        ]
        diff = DiffAnalyzer.compare_snapshots(prev_for_diff, curr_for_diff)

        # 7. Notify on new negatives
        new_negatives = [
            s
            for s in current_suggestions
            if s["text"] in {ns["text"] for ns in diff["new_suggestions"]}
            and s["sentiment"] == "negative"
        ]

        if new_negatives:
            await self._send_alerts(brand_name, new_negatives)

        summary = SentimentAnalyzer.get_summary(analyses)

        return {
            "brand_id": brand_id,
            "brand_name": brand_name,
            "snapshot_id": snapshot_id,
            "total_queries": len(raw_results),
            "total_suggestions": len(unique_suggestions),
            "summary": summary,
            "diff": diff["summary"],
            "new_negatives": len(new_negatives),
        }

    # ── scan all active brands ────────────────────────────────────────

    async def scan_all(
        self,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[dict]:
        """Scan every active brand and return a list of scan reports."""
        brands = self.db.list_brands(active_only=True)
        reports: list[dict] = []

        for i, brand in enumerate(brands, 1):
            if progress_callback is not None:
                progress_callback(i, len(brands), brand["name"])

            try:
                report = await self.scan_brand(brand)
                reports.append(report)
            except Exception:
                logger.exception("Error scanning brand %s", brand["name"])
                reports.append(
                    {
                        "brand_id": brand["id"],
                        "brand_name": brand["name"],
                        "error": True,
                    }
                )

        return reports

    # ── estimate ──────────────────────────────────────────────────────

    def get_scan_estimate(self, brand: dict) -> dict:
        """Estimate the number of queries and time for a brand scan.

        Returns::

            {"total_queries": int, "estimated_seconds": float}
        """
        keywords: list[str] = (
            json.loads(brand["keywords"])
            if isinstance(brand["keywords"], str)
            else brand["keywords"]
        )
        expand_az = bool(brand.get("expand_az", True))
        expand_turkish = bool(brand.get("expand_turkish", True))

        queries: list[str] = []
        for kw in keywords:
            queries.extend(
                self._tp.generate_query_variants(
                    kw, expand_az=expand_az, expand_turkish=expand_turkish
                )
            )
        # deduplicate
        unique = list(dict.fromkeys(queries))
        total = len(unique)

        delay = self.config.get("settings.request_delay", 1.5)
        workers = self.config.get("settings.max_workers", 3)
        estimated = (total / workers) * delay if workers > 0 else total * delay

        return {
            "total_queries": total,
            "estimated_seconds": round(estimated, 1),
        }

    # ── internal helpers ──────────────────────────────────────────────

    async def _send_alerts(self, brand_name: str, new_negatives: list[dict]) -> None:
        """Send alert notifications for new negative suggestions."""
        notifiers = get_notifiers(self.config)
        if not notifiers:
            return

        for notifier in notifiers:
            try:
                msg = notifier.format_new_negative_alert(brand_name, new_negatives)
                await notifier.send(msg)
            except AttributeError:
                # WebhookNotifier doesn't have format_new_negative_alert
                await notifier.send(
                    {
                        "event": "new_negative_suggestions",
                        "brand": brand_name,
                        "suggestions": new_negatives,
                    }
                )
            except Exception:
                logger.exception("Failed to send alert via %s", type(notifier).__name__)
            finally:
                await notifier.close()


# ── CLI entry point ──────────────────────────────────────────────────


def main() -> None:
    """CLI entry point: ``suggestguard-scan``."""
    parser = argparse.ArgumentParser(
        prog="suggestguard-scan",
        description="Run a SuggestGuard autocomplete scan.",
    )
    parser.add_argument(
        "--brand",
        type=str,
        default=None,
        help="Scan only this brand (by name). Omit to scan all active brands.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="suggestguard.yml",
        help="Path to configuration YAML (default: suggestguard.yml).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = SuggestGuardConfig(args.config)
    config.init_config()

    db = get_db(args.config)

    async def _run() -> None:
        engine = ScanEngine(db, config)
        try:
            if args.brand:
                brand = db.get_brand_by_name(args.brand)
                if brand is None:
                    logger.error("Brand %r not found.", args.brand)
                    sys.exit(1)
                report = await engine.scan_brand(brand)
                _print_report(report)
            else:
                reports = await engine.scan_all()
                for report in reports:
                    _print_report(report)
        finally:
            await engine.close()

    asyncio.run(_run())


def _print_report(report: dict) -> None:
    """Pretty-print a single scan report to stdout."""
    if report.get("error"):
        print(f"[ERROR] {report['brand_name']}: scan failed")
        return

    summary = report.get("summary", {})
    diff = report.get("diff", {})
    print(
        f"[OK] {report['brand_name']}: "
        f"{report['total_suggestions']} suggestions "
        f"(neg={summary.get('negative', 0)}, pos={summary.get('positive', 0)}, "
        f"neu={summary.get('neutral', 0)}) | "
        f"new={diff.get('new_count', 0)}, "
        f"gone={diff.get('disappeared_count', 0)}, "
        f"new_neg={report.get('new_negatives', 0)}"
    )
