"""Tests for suggestguard.analyzers.sentiment module."""

from __future__ import annotations

import pytest

from suggestguard.analyzers.sentiment import SentimentAnalyzer


@pytest.fixture
def sa() -> SentimentAnalyzer:
    return SentimentAnalyzer()


BRAND = "elma yayınevi"


# ── analyze (single) ────────────────────────────────────────────────


class TestAnalyze:
    def test_strong_negative_fraud(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi dolandırıcı", BRAND)
        assert r["sentiment"] == "negative"
        assert r["score"] == -0.9
        assert r["category"] == "fraud"
        assert "dolandırıcı" in r["matched_keywords"]
        assert r["confidence"] == 0.95

    def test_moderate_negative_complaint(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi şikayet", BRAND)
        assert r["sentiment"] == "negative"
        assert r["score"] == -0.6
        assert r["category"] == "complaint"
        assert "şikayet" in r["matched_keywords"]

    def test_mild_negative_trust(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi güvenilir mi", BRAND)
        assert r["sentiment"] == "negative"
        assert r["score"] == -0.3
        assert r["category"] == "trust"
        assert "güvenilir mi" in r["matched_keywords"]

    def test_positive(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi en iyi kitaplar", BRAND)
        assert r["sentiment"] == "positive"
        assert r["score"] == 0.6
        assert "en iyi" in r["matched_keywords"]
        assert r["category"] is None

    def test_neutral(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi adres", BRAND)
        assert r["sentiment"] == "neutral"
        assert r["score"] == 0.0
        assert r["matched_keywords"] == []
        assert r["category"] is None

    def test_strong_beats_moderate(self, sa: SentimentAnalyzer):
        """When both strong and moderate keywords exist, strong wins."""
        r = sa.analyze("elma yayınevi dolandırıcı şikayet", BRAND)
        assert r["score"] == -0.9
        assert r["category"] == "fraud"

    def test_case_insensitive(self, sa: SentimentAnalyzer):
        r = sa.analyze("ELMA YAYINEVİ ŞİKAYET", BRAND)
        assert r["sentiment"] == "negative"

    def test_legal_category(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi dava", BRAND)
        assert r["category"] == "legal"

    def test_quality_category(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi berbat", BRAND)
        assert r["category"] == "quality"

    def test_refund_category(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi iade", BRAND)
        assert r["category"] == "refund"

    def test_english_negative(self, sa: SentimentAnalyzer):
        r = sa.analyze("acme scam", "acme", language="en")
        assert r["sentiment"] == "negative"
        assert r["category"] == "fraud"

    def test_english_positive(self, sa: SentimentAnalyzer):
        r = sa.analyze("acme best product", "acme", language="en")
        assert r["sentiment"] == "positive"

    def test_english_neutral(self, sa: SentimentAnalyzer):
        r = sa.analyze("acme headquarters", "acme", language="en")
        assert r["sentiment"] == "neutral"

    def test_multiple_positive_keywords(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi en iyi tavsiye", BRAND)
        assert r["sentiment"] == "positive"
        assert "en iyi" in r["matched_keywords"]
        assert "tavsiye" in r["matched_keywords"]

    def test_brand_removed_before_analysis(self, sa: SentimentAnalyzer):
        """A keyword inside the brand name should NOT trigger a match."""
        # brand name itself is stripped; leftover text is "adres"
        r = sa.analyze("elma yayınevi adres", BRAND)
        assert r["sentiment"] == "neutral"

    def test_unknown_language_falls_back_to_tr(self, sa: SentimentAnalyzer):
        r = sa.analyze("elma yayınevi dolandırıcı", BRAND, language="de")
        assert r["sentiment"] == "negative"


# ── analyze_batch ────────────────────────────────────────────────────


class TestAnalyzeBatch:
    def test_batch_returns_correct_count(self, sa: SentimentAnalyzer):
        suggestions = [
            "elma yayınevi dolandırıcı",
            "elma yayınevi adres",
            "elma yayınevi en iyi",
        ]
        results = sa.analyze_batch(suggestions, BRAND)
        assert len(results) == 3

    def test_batch_sentiments(self, sa: SentimentAnalyzer):
        suggestions = [
            "elma yayınevi dolandırıcı",
            "elma yayınevi adres",
            "elma yayınevi en iyi",
        ]
        results = sa.analyze_batch(suggestions, BRAND)
        sentiments = [r["sentiment"] for r in results]
        assert sentiments == ["negative", "neutral", "positive"]

    def test_batch_empty(self, sa: SentimentAnalyzer):
        assert sa.analyze_batch([], BRAND) == []


# ── get_summary ──────────────────────────────────────────────────────


class TestGetSummary:
    def test_summary_counts(self, sa: SentimentAnalyzer):
        results = sa.analyze_batch(
            [
                "elma yayınevi dolandırıcı",
                "elma yayınevi şikayet",
                "elma yayınevi en iyi",
                "elma yayınevi adres",
                "elma yayınevi telefon",
            ],
            BRAND,
        )
        summary = sa.get_summary(results)
        assert summary["total"] == 5
        assert summary["negative"] == 2
        assert summary["positive"] == 1
        assert summary["neutral"] == 2
        assert summary["negative_ratio"] == 0.4

    def test_summary_top_categories(self, sa: SentimentAnalyzer):
        results = sa.analyze_batch(
            [
                "elma yayınevi dolandırıcı",
                "elma yayınevi sahte",
                "elma yayınevi şikayet",
            ],
            BRAND,
        )
        summary = sa.get_summary(results)
        cats = summary["top_categories"]
        assert cats["fraud"] == 2
        assert cats["complaint"] == 1
        # fraud should come first (higher count)
        assert list(cats.keys())[0] == "fraud"

    def test_summary_avg_score(self, sa: SentimentAnalyzer):
        results = sa.analyze_batch(
            [
                "elma yayınevi dolandırıcı",  # -0.9
                "elma yayınevi en iyi",  # +0.6
            ],
            BRAND,
        )
        summary = sa.get_summary(results)
        assert summary["avg_score"] == round((-0.9 + 0.6) / 2, 4)

    def test_summary_empty(self, sa: SentimentAnalyzer):
        summary = sa.get_summary([])
        assert summary["total"] == 0
        assert summary["negative_ratio"] == 0.0
        assert summary["avg_score"] == 0.0
        assert summary["top_categories"] == {}

    def test_summary_all_neutral(self, sa: SentimentAnalyzer):
        results = sa.analyze_batch(
            ["elma yayınevi adres", "elma yayınevi telefon"],
            BRAND,
        )
        summary = sa.get_summary(results)
        assert summary["negative"] == 0
        assert summary["positive"] == 0
        assert summary["neutral"] == 2
        assert summary["negative_ratio"] == 0.0
        assert summary["avg_score"] == 0.0
