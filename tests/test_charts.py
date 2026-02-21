"""Extra Plotly chart tests — figure structure, trace types, edge cases.

These supplement test_ui_components.py with more granular Figure checks.
"""

from __future__ import annotations

from unittest.mock import patch

import plotly.graph_objects as go
import pytest


@pytest.fixture(autouse=True)
def _mock_st():
    """Patch streamlit used inside charts module."""
    with patch("suggestguard.ui.components.charts.st"):
        yield


# ── _dark_layout helper ──────────────────────────────────────────────


class TestDarkLayoutHelper:
    def test_default_keys(self):
        from suggestguard.ui.components.charts import _dark_layout

        layout = _dark_layout()
        assert layout["plot_bgcolor"] == "rgba(0,0,0,0)"
        assert layout["paper_bgcolor"] == "rgba(0,0,0,0)"
        assert "color" in layout["font"]

    def test_overrides_merge(self):
        from suggestguard.ui.components.charts import _dark_layout

        layout = _dark_layout(title="My Title", showlegend=False)
        assert layout["title"] == "My Title"
        assert layout["showlegend"] is False
        # base keys still present
        assert layout["plot_bgcolor"] == "rgba(0,0,0,0)"

    def test_override_base_key(self):
        from suggestguard.ui.components.charts import _dark_layout

        layout = _dark_layout(plot_bgcolor="red")
        assert layout["plot_bgcolor"] == "red"


# ── sentiment_pie_chart ──────────────────────────────────────────────


class TestSentimentPieChartExtra:
    def test_donut_hole(self):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        fig = sentiment_pie_chart({"negative": 1, "positive": 2, "neutral": 3})
        assert fig.data[0].hole == 0.4

    def test_trace_type_is_pie(self):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        fig = sentiment_pie_chart({"negative": 1, "positive": 1, "neutral": 1})
        assert isinstance(fig.data[0], go.Pie)

    def test_labels(self):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        fig = sentiment_pie_chart({"negative": 1, "positive": 1, "neutral": 1})
        assert list(fig.data[0].labels) == ["Negatif", "Pozitif", "Nötr"]

    def test_zero_values(self):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        fig = sentiment_pie_chart({"negative": 0, "positive": 0, "neutral": 0})
        assert list(fig.data[0].values) == [0, 0, 0]


# ── negative_trend_line ──────────────────────────────────────────────


class TestNegativeTrendLineExtra:
    def test_trace_type_is_scatter(self):
        from suggestguard.ui.components.charts import negative_trend_line

        data = [{"date": "2025-01-01", "negative": 5}]
        fig = negative_trend_line(data)
        assert isinstance(fig.data[0], go.Scatter)

    def test_line_mode(self):
        from suggestguard.ui.components.charts import negative_trend_line

        fig = negative_trend_line([{"date": "2025-01-01", "negative": 3}])
        assert fig.data[0].mode == "lines+markers"

    def test_line_color(self):
        from suggestguard.ui.components.charts import COLOR_NEGATIVE, negative_trend_line

        fig = negative_trend_line([{"date": "2025-01-01", "negative": 1}])
        assert fig.data[0].line.color == COLOR_NEGATIVE

    def test_yaxis_rangemode(self):
        from suggestguard.ui.components.charts import negative_trend_line

        fig = negative_trend_line([{"date": "2025-01-01", "negative": 1}])
        assert fig.layout.yaxis.rangemode == "tozero"

    def test_missing_negative_key_defaults_to_zero(self):
        from suggestguard.ui.components.charts import negative_trend_line

        fig = negative_trend_line([{"date": "2025-01-01"}])
        assert list(fig.data[0].y) == [0]


# ── suggestion_position_chart ────────────────────────────────────────


class TestSuggestionPositionChartExtra:
    def test_trace_type(self):
        from suggestguard.ui.components.charts import suggestion_position_chart

        history = [{"snapshot_taken_at": "2025-01-01", "position": 1}]
        fig = suggestion_position_chart(history)
        assert isinstance(fig.data[0], go.Scatter)

    def test_line_color_is_primary(self):
        from suggestguard.ui.components.charts import COLOR_PRIMARY, suggestion_position_chart

        history = [{"snapshot_taken_at": "2025-01-01", "position": 1}]
        fig = suggestion_position_chart(history)
        assert fig.data[0].line.color == COLOR_PRIMARY

    def test_empty_history(self):
        from suggestguard.ui.components.charts import suggestion_position_chart

        fig = suggestion_position_chart([])
        assert len(fig.data[0].x) == 0


# ── sentiment_stacked_bar ────────────────────────────────────────────


class TestSentimentStackedBarExtra:
    def test_trace_types_are_bar(self):
        from suggestguard.ui.components.charts import sentiment_stacked_bar

        data = [{"date": "2025-01-01", "negative": 1, "positive": 2, "neutral": 3}]
        fig = sentiment_stacked_bar(data)
        for trace in fig.data:
            assert isinstance(trace, go.Bar)

    def test_multiple_days(self):
        from suggestguard.ui.components.charts import sentiment_stacked_bar

        data = [
            {"date": "2025-01-01", "negative": 1, "positive": 2, "neutral": 3},
            {"date": "2025-01-02", "negative": 4, "positive": 5, "neutral": 6},
        ]
        fig = sentiment_stacked_bar(data)
        assert list(fig.data[0].x) == ["2025-01-01", "2025-01-02"]
        assert list(fig.data[0].y) == [1, 4]  # negatives

    def test_missing_keys_default_to_zero(self):
        from suggestguard.ui.components.charts import sentiment_stacked_bar

        data = [{"date": "2025-01-01"}]
        fig = sentiment_stacked_bar(data)
        assert list(fig.data[0].y) == [0]  # negative
        assert list(fig.data[1].y) == [0]  # positive
        assert list(fig.data[2].y) == [0]  # neutral


# ── category_bar_chart ───────────────────────────────────────────────


class TestCategoryBarChartExtra:
    def test_returns_empty_figure_for_no_data(self):
        from suggestguard.ui.components.charts import category_bar_chart

        fig = category_bar_chart({})
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0

    def test_single_category(self):
        from suggestguard.ui.components.charts import category_bar_chart

        fig = category_bar_chart({"fraud": 7})
        assert list(fig.data[0].y) == ["fraud"]
        assert list(fig.data[0].x) == [7]

    def test_bar_color_is_negative(self):
        from suggestguard.ui.components.charts import COLOR_NEGATIVE, category_bar_chart

        fig = category_bar_chart({"fraud": 1})
        assert fig.data[0].marker.color == COLOR_NEGATIVE
