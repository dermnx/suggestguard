"""Table components for displaying suggestion data."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from suggestguard.ui.components import format_date, sentiment_emoji

# ── suggestions table ────────────────────────────────────────────────


def suggestions_table(suggestions: list[dict]) -> None:
    """Render a sortable dataframe of suggestions with emoji sentiments.

    Each item in *suggestions* should have at least:
    ``text``, ``sentiment``, ``sentiment_score``, ``category``,
    ``position``, ``times_seen``, ``first_seen``, ``last_seen``.
    """
    if not suggestions:
        st.info("Gösterilecek öneri yok.")
        return

    rows = []
    for s in suggestions:
        rows.append(
            {
                "Öneri": s.get("text", ""),
                "Duygu": sentiment_emoji(s.get("sentiment")),
                "Skor": s.get("sentiment_score", 0),
                "Kategori": s.get("category") or "—",
                "Pozisyon": s.get("position") or "—",
                "Görülme": s.get("times_seen", 1),
                "İlk Görülme": format_date(s.get("first_seen")),
                "Son Görülme": format_date(s.get("last_seen")),
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Skor": st.column_config.NumberColumn(format="%.2f"),
            "Görülme": st.column_config.NumberColumn(format="%d"),
        },
    )


# ── diff table (tabbed) ─────────────────────────────────────────────


def diff_table(diff: dict) -> None:
    """Render a diff report in three tabs: Yeni | Kaybolan | Değişen.

    *diff* is the dict returned by ``DiffAnalyzer.compare_snapshots()``.
    """
    new = diff.get("new_suggestions", [])
    gone = diff.get("disappeared", [])
    changed = diff.get("position_changes", [])

    tab_new, tab_gone, tab_changed = st.tabs(
        [
            f"🆕 Yeni ({len(new)})",
            f"❌ Kaybolan ({len(gone)})",
            f"🔄 Değişen ({len(changed)})",
        ]
    )

    with tab_new:
        if new:
            df = pd.DataFrame(
                [
                    {
                        "Öneri": s.get("text", ""),
                        "Pozisyon": s.get("position", "—"),
                    }
                    for s in new
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Yeni öneri yok.")

    with tab_gone:
        if gone:
            df = pd.DataFrame(
                [
                    {
                        "Öneri": s.get("text", ""),
                        "Pozisyon": s.get("position", "—"),
                    }
                    for s in gone
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Kaybolan öneri yok.")

    with tab_changed:
        if changed:
            df = pd.DataFrame(
                [
                    {
                        "Öneri": s.get("text", ""),
                        "Eski Pozisyon": s.get("old_position", "—"),
                        "Yeni Pozisyon": s.get("new_position", "—"),
                        "Değişim": _position_delta(s.get("old_position"), s.get("new_position")),
                    }
                    for s in changed
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Pozisyon değişikliği yok.")


# ── campaign comparison table ────────────────────────────────────────


def campaign_comparison_table(comparison: dict) -> None:
    """Render a before/during comparison table for a campaign.

    *comparison* is the dict returned by ``Database.get_campaign_comparison()``:

    - campaign: {name, started_at, ended_at, ...}
    - before:   {negative, positive, neutral, total}
    - during:   {negative, positive, neutral, total}
    """
    if not comparison:
        st.info("Kampanya verisi bulunamadı.")
        return

    campaign = comparison.get("campaign", {})
    before = comparison.get("before", {})
    during = comparison.get("during", {})

    st.subheader(f"📊 {campaign.get('name', 'Kampanya')}")
    st.caption(
        f"{format_date(campaign.get('started_at'))} — "
        f"{format_date(campaign.get('ended_at')) or 'Devam ediyor'}"
    )

    rows = []
    for label, key in [
        ("Toplam", "total"),
        ("Negatif", "negative"),
        ("Pozitif", "positive"),
        ("Nötr", "neutral"),
    ]:
        b = before.get(key) or 0
        d = during.get(key) or 0
        delta = d - b
        rows.append(
            {
                "Metrik": label,
                "Önce": b,
                "Kampanya Sırasında": d,
                "Değişim": f"{'+' if delta > 0 else ''}{delta}",
            }
        )

    # negative ratio
    b_total = before.get("total") or 0
    d_total = during.get("total") or 0
    b_neg = before.get("negative") or 0
    d_neg = during.get("negative") or 0
    b_ratio = round(b_neg / b_total * 100, 1) if b_total else 0.0
    d_ratio = round(d_neg / d_total * 100, 1) if d_total else 0.0
    ratio_delta = round(d_ratio - b_ratio, 1)
    rows.append(
        {
            "Metrik": "Negatif Oranı (%)",
            "Önce": f"%{b_ratio}",
            "Kampanya Sırasında": f"%{d_ratio}",
            "Değişim": f"{'+' if ratio_delta > 0 else ''}{ratio_delta}%",
        }
    )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── internal helpers ─────────────────────────────────────────────────


def _position_delta(old: int | None, new: int | None) -> str:
    """Return a human-readable position change string."""
    if old is None or new is None:
        return "—"
    diff = old - new  # lower position = higher rank
    if diff > 0:
        return f"↑ {diff}"
    elif diff < 0:
        return f"↓ {abs(diff)}"
    return "—"
