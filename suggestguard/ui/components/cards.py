"""Metric card components for displaying KPIs."""

from __future__ import annotations

import streamlit as st


def metric_card(
    label: str,
    value: str | int | float,
    delta: str | int | float | None = None,
    delta_color: str = "normal",
) -> None:
    """Render a single ``st.metric`` inside a styled container.

    *delta_color* accepts ``"normal"`` (green up / red down),
    ``"inverse"`` (red up / green down), or ``"off"``.
    """
    with st.container(border=True):
        st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def brand_health_card(brand_name: str, stats: dict) -> None:
    """Render a brand health overview card.

    *stats* is the dict returned by ``Database.get_brand_stats()``:

    - total_suggestions, negative_count, positive_count, neutral_count,
      negative_ratio, last_scan, total_scans, new_last_7d, disappeared_last_7d

    Displays 4 core metrics, a negative-ratio progress bar, and a
    computed **Health Score** (100 − negative_ratio × 100).
    """
    total = stats.get("total_suggestions", 0)
    negative = stats.get("negative_count", 0)
    positive = stats.get("positive_count", 0)
    neutral = stats.get("neutral_count", 0)
    neg_ratio = stats.get("negative_ratio", 0.0)
    health_score = round(100 - neg_ratio * 100, 1)

    with st.container(border=True):
        st.subheader(f"🏢 {brand_name}")

        # ── 4 metrics ────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Toplam Öneri", total)
        with c2:
            st.metric(
                "Negatif",
                negative,
                delta=f"{stats.get('new_last_7d', 0)} yeni (7g)",
                delta_color="inverse",
            )
        with c3:
            st.metric("Pozitif", positive)
        with c4:
            st.metric("Nötr", neutral)

        # ── negative ratio bar ───────────────────────────────────
        st.caption("Negatif Oranı")
        st.progress(min(neg_ratio, 1.0))

        # ── health score ─────────────────────────────────────────
        left, right = st.columns([3, 1])
        with left:
            if health_score >= 70:
                st.success(f"Sağlık Skoru: **{health_score}**")
            elif health_score >= 40:
                st.warning(f"Sağlık Skoru: **{health_score}**")
            else:
                st.error(f"Sağlık Skoru: **{health_score}**")
        with right:
            last_scan = stats.get("last_scan")
            st.caption(f"Son tarama: {last_scan or '—'}")


def alert_card(
    title: str,
    message: str,
    level: str = "info",
) -> None:
    """Render a coloured alert box.

    *level* is one of ``"success"``, ``"warning"``, ``"error"``, ``"info"``.
    """
    renderers = {
        "success": st.success,
        "warning": st.warning,
        "error": st.error,
        "info": st.info,
    }
    renderer = renderers.get(level, st.info)
    renderer(f"**{title}**\n\n{message}")
