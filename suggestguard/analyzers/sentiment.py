"""Keyword-based sentiment analysis for autocomplete suggestions."""

from __future__ import annotations

from suggestguard.analyzers.turkish import TurkishTextProcessor

_tp = TurkishTextProcessor()


class SentimentAnalyzer:
    """Rule-based sentiment analyser using keyword dictionaries."""

    # ── negative keyword dictionaries (by severity) ──────────────────

    NEGATIVE_KEYWORDS: dict[str, dict[str, list[str]]] = {
        "tr": {
            "strong": [
                "dolandırıcı",
                "dolandırıcılık",
                "sahte",
                "tehlikeli",
                "yasadışı",
                "suç",
                "hırsız",
            ],
            "moderate": [
                "şikayet",
                "şikayetvar",
                "sorun",
                "problem",
                "kötü",
                "rezalet",
                "berbat",
                "mağdur",
                "zararlı",
                "pişman",
                "kaçın",
            ],
            "mild": [
                "kapandı mı",
                "güvenilir mi",
                "batık",
                "iflas",
                "dava",
                "yasal",
                "iptal",
                "iade",
            ],
        },
        "en": {
            "strong": ["scam", "fraud", "illegal", "dangerous", "criminal"],
            "moderate": [
                "complaint",
                "worst",
                "terrible",
                "awful",
                "ripoff",
                "avoid",
                "horrible",
            ],
            "mild": [
                "lawsuit",
                "class action",
                "shut down",
                "bankrupt",
                "refund",
                "cancel",
            ],
        },
    }

    # ── positive keyword lists ───────────────────────────────────────

    POSITIVE_KEYWORDS: dict[str, list[str]] = {
        "tr": [
            "en iyi",
            "tavsiye",
            "güvenilir",
            "kaliteli",
            "başarılı",
            "ödüllü",
            "popüler",
            "mükemmel",
            "harika",
            "indirim",
            "kampanya",
        ],
        "en": [
            "best",
            "recommended",
            "award",
            "trusted",
            "top rated",
            "excellent",
            "popular",
            "amazing",
        ],
    }

    # ── category mapping ─────────────────────────────────────────────

    CATEGORIES: dict[str, list[str]] = {
        "fraud": ["dolandırıcı", "sahte", "scam", "fraud", "fake"],
        "complaint": ["şikayet", "sorun", "problem", "complaint"],
        "legal": ["dava", "yasal", "lawsuit", "yasadışı"],
        "quality": ["kötü", "berbat", "rezalet", "worst", "terrible"],
        "trust": ["güvenilir mi", "kapandı mı", "batık", "iflas"],
        "refund": ["iade", "iptal", "refund", "cancel"],
    }

    # severity → (score, confidence)
    _SEVERITY_MAP: dict[str, tuple[float, float]] = {
        "strong": (-0.9, 0.95),
        "moderate": (-0.6, 0.80),
        "mild": (-0.3, 0.65),
    }

    # ── public API ───────────────────────────────────────────────────

    def analyze(
        self,
        text: str,
        brand_name: str,
        language: str = "tr",
    ) -> dict:
        """Analyse a single suggestion and return a sentiment dict.

        Returns::

            {
                "sentiment": "positive" | "negative" | "neutral",
                "score": float,        # -1.0 … +1.0
                "category": str | None,
                "matched_keywords": list[str],
                "confidence": float,   # 0.0 … 1.0
            }
        """
        normalized = _tp.normalize(text)
        brand_lower = _tp.normalize(brand_name)
        cleaned = normalized.replace(brand_lower, "").strip()

        # --- check negatives (strongest match wins) ---
        neg_dict = self.NEGATIVE_KEYWORDS.get(language, self.NEGATIVE_KEYWORDS["tr"])
        for severity in ("strong", "moderate", "mild"):
            matched = [kw for kw in neg_dict[severity] if kw in cleaned]
            if matched:
                score, confidence = self._SEVERITY_MAP[severity]
                category = self._detect_category(matched)
                return {
                    "sentiment": "negative",
                    "score": score,
                    "category": category,
                    "matched_keywords": matched,
                    "confidence": confidence,
                }

        # --- check positives ---
        pos_list = self.POSITIVE_KEYWORDS.get(language, self.POSITIVE_KEYWORDS["tr"])
        matched = [kw for kw in pos_list if kw in cleaned]
        if matched:
            return {
                "sentiment": "positive",
                "score": 0.6,
                "category": None,
                "matched_keywords": matched,
                "confidence": 0.75,
            }

        # --- neutral fallback ---
        return {
            "sentiment": "neutral",
            "score": 0.0,
            "category": None,
            "matched_keywords": [],
            "confidence": 0.50,
        }

    def analyze_batch(
        self,
        suggestions: list[str],
        brand_name: str,
        language: str = "tr",
    ) -> list[dict]:
        """Analyse a list of suggestions, returning one dict per item."""
        return [self.analyze(s, brand_name, language) for s in suggestions]

    @staticmethod
    def get_summary(results: list[dict]) -> dict:
        """Aggregate a list of analysis results into a summary dict.

        Returns::

            {
                "total": int,
                "negative": int,
                "positive": int,
                "neutral": int,
                "negative_ratio": float,
                "top_categories": dict[str, int],
                "avg_score": float,
            }
        """
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "negative": 0,
                "positive": 0,
                "neutral": 0,
                "negative_ratio": 0.0,
                "top_categories": {},
                "avg_score": 0.0,
            }

        negative = sum(1 for r in results if r["sentiment"] == "negative")
        positive = sum(1 for r in results if r["sentiment"] == "positive")
        neutral = sum(1 for r in results if r["sentiment"] == "neutral")

        categories: dict[str, int] = {}
        for r in results:
            cat = r.get("category")
            if cat:
                categories[cat] = categories.get(cat, 0) + 1
        top_categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))

        avg_score = round(sum(r["score"] for r in results) / total, 4)

        return {
            "total": total,
            "negative": negative,
            "positive": positive,
            "neutral": neutral,
            "negative_ratio": round(negative / total, 4),
            "top_categories": top_categories,
            "avg_score": avg_score,
        }

    # ── internal helpers ─────────────────────────────────────────────

    def _detect_category(self, matched_keywords: list[str]) -> str | None:
        """Return the first matching category for *matched_keywords*."""
        for cat, cat_keywords in self.CATEGORIES.items():
            for kw in matched_keywords:
                if kw in cat_keywords:
                    return cat
        return None
