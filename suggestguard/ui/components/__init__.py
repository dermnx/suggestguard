"""Reusable Streamlit UI components."""

from __future__ import annotations

# ── helper utilities (used by cards, charts, tables) ─────────────────


_SENTIMENT_EMOJI: dict[str | None, str] = {
    "negative": "🔴 Negatif",
    "positive": "🟢 Pozitif",
    "neutral": "⚪ Nötr",
}


def sentiment_emoji(sentiment: str | None) -> str:
    """Return an emoji-prefixed label for a sentiment value."""
    return _SENTIMENT_EMOJI.get(sentiment, "❓ Bilinmiyor")


def format_date(value: str | None) -> str:
    """Return a human-friendly date string (or '—' for None/empty)."""
    if not value:
        return "—"
    # strip seconds if present: "2025-01-15 14:30:25" → "2025-01-15 14:30"
    if len(value) >= 16:
        return value[:16]
    return value
