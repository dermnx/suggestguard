"""Plotly chart components for visualizing suggestion trends."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# ── shared colours & layout ──────────────────────────────────────────

COLOR_NEGATIVE = "#EF4444"
COLOR_POSITIVE = "#22C55E"
COLOR_NEUTRAL = "#6B7280"
COLOR_TEXT = "#E2E8F0"
COLOR_PRIMARY = "#3B82F6"


def _dark_layout(**overrides) -> dict:
    """Return a base Plotly layout dict for the dark Streamlit theme."""
    base = dict(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLOR_TEXT),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    base.update(overrides)
    return base


# ── sentiment pie chart ──────────────────────────────────────────────


def sentiment_pie_chart(summary: dict) -> go.Figure:
    """Render a sentiment breakdown pie chart.

    *summary* is the dict from ``SentimentAnalyzer.get_summary()``.
    Returns the Plotly ``Figure`` and displays it via ``st.plotly_chart``.
    """
    labels = ["Negatif", "Pozitif", "Nötr"]
    values = [
        summary.get("negative", 0),
        summary.get("positive", 0),
        summary.get("neutral", 0),
    ]
    colors = [COLOR_NEGATIVE, COLOR_POSITIVE, COLOR_NEUTRAL]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors),
                hole=0.4,
                textinfo="label+percent",
                textfont=dict(color=COLOR_TEXT),
            )
        ]
    )
    fig.update_layout(**_dark_layout(title="Duygu Dağılımı", showlegend=True))
    st.plotly_chart(fig, use_container_width=True)
    return fig


# ── negative trend line ──────────────────────────────────────────────


def negative_trend_line(daily_data: list[dict]) -> go.Figure:
    """Render a daily negative-count line chart.

    *daily_data* is a list of ``{"date": str, "negative": int, ...}`` dicts
    (from ``Database.get_daily_sentiment_counts()``).
    """
    dates = [d["date"] for d in daily_data]
    negatives = [d.get("negative", 0) for d in daily_data]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=dates,
                y=negatives,
                mode="lines+markers",
                name="Negatif",
                line=dict(color=COLOR_NEGATIVE, width=2),
                marker=dict(size=6),
            )
        ]
    )
    fig.update_layout(
        **_dark_layout(
            title="Günlük Negatif Öneri Sayısı",
            xaxis=dict(title="Tarih"),
            yaxis=dict(title="Negatif Sayısı", rangemode="tozero"),
        )
    )
    st.plotly_chart(fig, use_container_width=True)
    return fig


# ── suggestion position chart ────────────────────────────────────────


def suggestion_position_chart(history: list[dict]) -> go.Figure:
    """Render the position history of a single suggestion over time.

    *history* is a list of ``{"snapshot_taken_at": str, "position": int, ...}``
    dicts (from ``Database.get_suggestion_history()``).
    """
    dates = [h["snapshot_taken_at"] for h in history]
    positions = [h.get("position") for h in history]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=dates,
                y=positions,
                mode="lines+markers",
                name="Pozisyon",
                line=dict(color=COLOR_PRIMARY, width=2),
                marker=dict(size=8),
            )
        ]
    )
    fig.update_layout(
        **_dark_layout(
            title="Öneri Pozisyon Değişimi",
            xaxis=dict(title="Tarih"),
            yaxis=dict(
                title="Pozisyon",
                autorange="reversed",
                rangemode="tozero",
            ),
        )
    )
    st.plotly_chart(fig, use_container_width=True)
    return fig


# ── sentiment stacked bar ────────────────────────────────────────────


def sentiment_stacked_bar(daily_data: list[dict]) -> go.Figure:
    """Render a daily stacked bar chart of sentiment counts.

    *daily_data* is the same format as ``negative_trend_line``.
    """
    dates = [d["date"] for d in daily_data]
    negatives = [d.get("negative", 0) for d in daily_data]
    positives = [d.get("positive", 0) for d in daily_data]
    neutrals = [d.get("neutral", 0) for d in daily_data]

    fig = go.Figure(
        data=[
            go.Bar(name="Negatif", x=dates, y=negatives, marker_color=COLOR_NEGATIVE),
            go.Bar(name="Pozitif", x=dates, y=positives, marker_color=COLOR_POSITIVE),
            go.Bar(name="Nötr", x=dates, y=neutrals, marker_color=COLOR_NEUTRAL),
        ]
    )
    fig.update_layout(
        **_dark_layout(
            title="Günlük Duygu Dağılımı",
            barmode="stack",
            xaxis=dict(title="Tarih"),
            yaxis=dict(title="Öneri Sayısı", rangemode="tozero"),
        )
    )
    st.plotly_chart(fig, use_container_width=True)
    return fig


# ── category horizontal bar ──────────────────────────────────────────


def category_bar_chart(categories: dict[str, int]) -> go.Figure:
    """Render a horizontal bar chart of negative categories.

    *categories* is ``{"fraud": 5, "complaint": 3, ...}`` — the
    ``top_categories`` dict from ``SentimentAnalyzer.get_summary()``.
    """
    if not categories:
        st.info("Henüz kategori verisi yok.")
        return go.Figure()

    # sort ascending so largest bar is on top
    sorted_cats = sorted(categories.items(), key=lambda x: x[1])
    labels = [c[0] for c in sorted_cats]
    values = [c[1] for c in sorted_cats]

    fig = go.Figure(
        data=[
            go.Bar(
                x=values,
                y=labels,
                orientation="h",
                marker_color=COLOR_NEGATIVE,
            )
        ]
    )
    fig.update_layout(
        **_dark_layout(
            title="Negatif Kategori Dağılımı",
            xaxis=dict(title="Sayı", rangemode="tozero"),
            yaxis=dict(title=""),
        )
    )
    st.plotly_chart(fig, use_container_width=True)
    return fig
