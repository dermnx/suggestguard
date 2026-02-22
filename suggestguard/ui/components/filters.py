"""Reusable filter components for Streamlit pages."""

from __future__ import annotations

import streamlit as st

from suggestguard.database import Database

# ── constants ──────────────────────────────────────────────────────────

SENTIMENT_OPTIONS = ["Tümü", "🔴 Negatif", "🟢 Pozitif", "⚪ Nötr"]

SENTIMENT_VALUE_MAP: dict[str, str | None] = {
    "Tümü": None,
    "🔴 Negatif": "negative",
    "🟢 Pozitif": "positive",
    "⚪ Nötr": "neutral",
}


# ── brand selector ─────────────────────────────────────────────────────


def require_brands(db: Database) -> list[dict]:
    """Fetch active brands and stop page if none exist.

    Returns the brand list on success; calls ``st.stop()`` otherwise.
    """
    brands = db.list_brands(active_only=True)
    if not brands:
        st.info("Henüz marka eklenmemiş. Ana sayfadan marka ekleyin veya demo veri oluşturun.")
        st.page_link("app.py", label="← Ana Sayfa", use_container_width=False)
        st.stop()
    return brands


def brand_selector(brands: list[dict], *, label: str = "Marka Seçin") -> dict:
    """Render a brand selectbox and return the selected brand dict."""
    brand_names = [b["name"] for b in brands]
    brand_map = {b["name"]: b for b in brands}
    selected_name = st.selectbox(label, brand_names, index=0)
    return brand_map[selected_name]
