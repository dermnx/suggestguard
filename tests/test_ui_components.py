"""Tests for suggestguard.ui.components (helpers, charts, cards, tables).

Streamlit rendering calls are patched out — we test data logic and
Plotly figure structure, not actual DOM output.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import plotly.graph_objects as go
import pytest

from suggestguard.ui.components import format_date, sentiment_emoji

# ══════════════════════════════════════════════════════════════════════
# Helper utilities
# ══════════════════════════════════════════════════════════════════════


class TestSentimentEmoji:
    def test_negative(self):
        assert "🔴" in sentiment_emoji("negative")

    def test_positive(self):
        assert "🟢" in sentiment_emoji("positive")

    def test_neutral(self):
        assert "⚪" in sentiment_emoji("neutral")

    def test_unknown(self):
        assert "❓" in sentiment_emoji("other")

    def test_none(self):
        assert "❓" in sentiment_emoji(None)


class TestFormatDate:
    def test_full_datetime(self):
        assert format_date("2025-01-15 14:30:25") == "2025-01-15 14:30"

    def test_short_datetime(self):
        assert format_date("2025-01-15 14:30") == "2025-01-15 14:30"

    def test_date_only(self):
        assert format_date("2025-01-15") == "2025-01-15"

    def test_none(self):
        assert format_date(None) == "—"

    def test_empty_string(self):
        assert format_date("") == "—"


# ══════════════════════════════════════════════════════════════════════
# Charts — verify Plotly figure structure (st.plotly_chart is mocked)
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_streamlit():
    """Patch all st.* calls used by the component modules."""
    with (
        patch("suggestguard.ui.components.charts.st") as mock_st,
        patch("suggestguard.ui.components.cards.st") as mock_cards_st,
        patch("suggestguard.ui.components.tables.st") as mock_tables_st,
    ):
        # st.columns needs to return a list matching the requested count
        def _columns_side_effect(spec, **kwargs):
            n = spec if isinstance(spec, int) else len(spec)
            return [MagicMock() for _ in range(n)]

        mock_cards_st.columns.side_effect = _columns_side_effect
        mock_cards_st.container.return_value.__enter__ = MagicMock(return_value=None)
        mock_cards_st.container.return_value.__exit__ = MagicMock(return_value=False)

        mock_tables_st.tabs.return_value = [
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]
        for tab in mock_tables_st.tabs.return_value:
            tab.__enter__ = MagicMock(return_value=None)
            tab.__exit__ = MagicMock(return_value=False)

        yield {
            "charts": mock_st,
            "cards": mock_cards_st,
            "tables": mock_tables_st,
        }


class TestSentimentPieChart:
    def test_returns_figure(self):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        summary = {"negative": 3, "positive": 5, "neutral": 2}
        fig = sentiment_pie_chart(summary)
        assert isinstance(fig, go.Figure)

    def test_pie_values(self):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        summary = {"negative": 10, "positive": 20, "neutral": 5}
        fig = sentiment_pie_chart(summary)
        values = fig.data[0].values
        assert list(values) == [10, 20, 5]

    def test_pie_colors(self):
        from suggestguard.ui.components.charts import (
            COLOR_NEGATIVE,
            COLOR_NEUTRAL,
            COLOR_POSITIVE,
            sentiment_pie_chart,
        )

        fig = sentiment_pie_chart({"negative": 1, "positive": 1, "neutral": 1})
        colors = fig.data[0].marker.colors
        assert colors == (COLOR_NEGATIVE, COLOR_POSITIVE, COLOR_NEUTRAL)

    def test_calls_plotly_chart(self, _mock_streamlit):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        sentiment_pie_chart({"negative": 1, "positive": 1, "neutral": 1})
        _mock_streamlit["charts"].plotly_chart.assert_called_once()

    def test_empty_summary(self):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        fig = sentiment_pie_chart({})
        assert list(fig.data[0].values) == [0, 0, 0]


class TestNegativeTrendLine:
    def test_returns_figure(self):
        from suggestguard.ui.components.charts import negative_trend_line

        data = [
            {"date": "2025-01-01", "negative": 5},
            {"date": "2025-01-02", "negative": 3},
        ]
        fig = negative_trend_line(data)
        assert isinstance(fig, go.Figure)

    def test_line_data(self):
        from suggestguard.ui.components.charts import negative_trend_line

        data = [
            {"date": "2025-01-01", "negative": 5},
            {"date": "2025-01-02", "negative": 8},
        ]
        fig = negative_trend_line(data)
        assert list(fig.data[0].y) == [5, 8]
        assert list(fig.data[0].x) == ["2025-01-01", "2025-01-02"]

    def test_empty_data(self):
        from suggestguard.ui.components.charts import negative_trend_line

        fig = negative_trend_line([])
        assert len(fig.data[0].x) == 0


class TestSuggestionPositionChart:
    def test_returns_figure(self):
        from suggestguard.ui.components.charts import suggestion_position_chart

        history = [
            {"snapshot_taken_at": "2025-01-01 10:00", "position": 3},
            {"snapshot_taken_at": "2025-01-02 10:00", "position": 1},
        ]
        fig = suggestion_position_chart(history)
        assert isinstance(fig, go.Figure)

    def test_reversed_y_axis(self):
        from suggestguard.ui.components.charts import suggestion_position_chart

        history = [{"snapshot_taken_at": "2025-01-01", "position": 5}]
        fig = suggestion_position_chart(history)
        assert fig.layout.yaxis.autorange == "reversed"

    def test_position_values(self):
        from suggestguard.ui.components.charts import suggestion_position_chart

        history = [
            {"snapshot_taken_at": "2025-01-01", "position": 5},
            {"snapshot_taken_at": "2025-01-02", "position": 2},
        ]
        fig = suggestion_position_chart(history)
        assert list(fig.data[0].y) == [5, 2]


class TestSentimentStackedBar:
    def test_returns_figure(self):
        from suggestguard.ui.components.charts import sentiment_stacked_bar

        data = [{"date": "2025-01-01", "negative": 2, "positive": 5, "neutral": 3}]
        fig = sentiment_stacked_bar(data)
        assert isinstance(fig, go.Figure)

    def test_stacked_barmode(self):
        from suggestguard.ui.components.charts import sentiment_stacked_bar

        fig = sentiment_stacked_bar(
            [{"date": "2025-01-01", "negative": 1, "positive": 1, "neutral": 1}]
        )
        assert fig.layout.barmode == "stack"

    def test_three_traces(self):
        from suggestguard.ui.components.charts import sentiment_stacked_bar

        fig = sentiment_stacked_bar(
            [{"date": "2025-01-01", "negative": 1, "positive": 2, "neutral": 3}]
        )
        assert len(fig.data) == 3
        assert fig.data[0].name == "Negatif"
        assert fig.data[1].name == "Pozitif"
        assert fig.data[2].name == "Nötr"


class TestCategoryBarChart:
    def test_returns_figure(self):
        from suggestguard.ui.components.charts import category_bar_chart

        cats = {"fraud": 5, "complaint": 3, "quality": 1}
        fig = category_bar_chart(cats)
        assert isinstance(fig, go.Figure)

    def test_horizontal_orientation(self):
        from suggestguard.ui.components.charts import category_bar_chart

        fig = category_bar_chart({"fraud": 5})
        assert fig.data[0].orientation == "h"

    def test_sorted_ascending(self):
        from suggestguard.ui.components.charts import category_bar_chart

        cats = {"fraud": 10, "complaint": 3, "quality": 7}
        fig = category_bar_chart(cats)
        # ascending so largest on top
        assert list(fig.data[0].y) == ["complaint", "quality", "fraud"]

    def test_empty_categories(self, _mock_streamlit):
        from suggestguard.ui.components.charts import category_bar_chart

        category_bar_chart({})
        _mock_streamlit["charts"].info.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
# Charts — dark theme layout
# ══════════════════════════════════════════════════════════════════════


class TestDarkLayout:
    def test_transparent_backgrounds(self):
        from suggestguard.ui.components.charts import sentiment_pie_chart

        fig = sentiment_pie_chart({"negative": 1, "positive": 1, "neutral": 1})
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"

    def test_font_color(self):
        from suggestguard.ui.components.charts import COLOR_TEXT, sentiment_pie_chart

        fig = sentiment_pie_chart({"negative": 1, "positive": 1, "neutral": 1})
        assert fig.layout.font.color == COLOR_TEXT


# ══════════════════════════════════════════════════════════════════════
# Cards
# ══════════════════════════════════════════════════════════════════════


class TestMetricCard:
    def test_calls_metric(self, _mock_streamlit):
        from suggestguard.ui.components.cards import metric_card

        metric_card("Toplam", 42, delta="+5")
        _mock_streamlit["cards"].metric.assert_called_once_with(
            label="Toplam", value=42, delta="+5", delta_color="normal"
        )

    def test_inverse_delta_color(self, _mock_streamlit):
        from suggestguard.ui.components.cards import metric_card

        metric_card("Negatif", 10, delta="+3", delta_color="inverse")
        _mock_streamlit["cards"].metric.assert_called_once_with(
            label="Negatif", value=10, delta="+3", delta_color="inverse"
        )


class TestBrandHealthCard:
    def test_health_score_high(self, _mock_streamlit):
        from suggestguard.ui.components.cards import brand_health_card

        stats = {
            "total_suggestions": 100,
            "negative_count": 10,
            "positive_count": 60,
            "neutral_count": 30,
            "negative_ratio": 0.1,
            "last_scan": "2025-01-15 14:30:00",
            "total_scans": 5,
            "new_last_7d": 3,
            "disappeared_last_7d": 1,
        }
        brand_health_card("TestBrand", stats)
        # health = 100 - 10 = 90 → st.success
        _mock_streamlit["cards"].success.assert_called_once()
        call_args = _mock_streamlit["cards"].success.call_args[0][0]
        assert "90.0" in call_args

    def test_health_score_medium(self, _mock_streamlit):
        from suggestguard.ui.components.cards import brand_health_card

        stats = {
            "total_suggestions": 100,
            "negative_count": 50,
            "positive_count": 30,
            "neutral_count": 20,
            "negative_ratio": 0.5,
            "new_last_7d": 0,
        }
        brand_health_card("TestBrand", stats)
        # health = 100 - 50 = 50 → st.warning
        _mock_streamlit["cards"].warning.assert_called()

    def test_health_score_low(self, _mock_streamlit):
        from suggestguard.ui.components.cards import brand_health_card

        stats = {
            "total_suggestions": 100,
            "negative_count": 80,
            "positive_count": 10,
            "neutral_count": 10,
            "negative_ratio": 0.8,
            "new_last_7d": 0,
        }
        brand_health_card("TestBrand", stats)
        # health = 100 - 80 = 20 → st.error
        _mock_streamlit["cards"].error.assert_called()


class TestAlertCard:
    def test_success(self, _mock_streamlit):
        from suggestguard.ui.components.cards import alert_card

        alert_card("Başarılı", "İşlem tamamlandı", "success")
        _mock_streamlit["cards"].success.assert_called_once()

    def test_warning(self, _mock_streamlit):
        from suggestguard.ui.components.cards import alert_card

        alert_card("Dikkat", "Yüksek negatif oran", "warning")
        _mock_streamlit["cards"].warning.assert_called_once()

    def test_error(self, _mock_streamlit):
        from suggestguard.ui.components.cards import alert_card

        alert_card("Hata", "Bağlantı hatası", "error")
        _mock_streamlit["cards"].error.assert_called_once()

    def test_info(self, _mock_streamlit):
        from suggestguard.ui.components.cards import alert_card

        alert_card("Bilgi", "Tarama devam ediyor", "info")
        _mock_streamlit["cards"].info.assert_called_once()

    def test_unknown_level_falls_back_to_info(self, _mock_streamlit):
        from suggestguard.ui.components.cards import alert_card

        alert_card("Test", "mesaj", "nonexistent")
        _mock_streamlit["cards"].info.assert_called_once()

    def test_message_contains_title_and_body(self, _mock_streamlit):
        from suggestguard.ui.components.cards import alert_card

        alert_card("Başlık", "İçerik metni", "info")
        call_arg = _mock_streamlit["cards"].info.call_args[0][0]
        assert "Başlık" in call_arg
        assert "İçerik metni" in call_arg


# ══════════════════════════════════════════════════════════════════════
# Tables
# ══════════════════════════════════════════════════════════════════════


class TestSuggestionsTable:
    def test_empty_shows_info(self, _mock_streamlit):
        from suggestguard.ui.components.tables import suggestions_table

        suggestions_table([])
        _mock_streamlit["tables"].info.assert_called_once()

    def test_renders_dataframe(self, _mock_streamlit):
        from suggestguard.ui.components.tables import suggestions_table

        data = [
            {
                "text": "marka dolandırıcı",
                "sentiment": "negative",
                "sentiment_score": -0.9,
                "category": "fraud",
                "position": 1,
                "times_seen": 3,
                "first_seen": "2025-01-10 10:00:00",
                "last_seen": "2025-01-15 14:30:00",
            }
        ]
        suggestions_table(data)
        _mock_streamlit["tables"].dataframe.assert_called_once()

    def test_dataframe_columns(self, _mock_streamlit):

        from suggestguard.ui.components.tables import suggestions_table

        data = [
            {
                "text": "test",
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "category": None,
                "position": 2,
                "times_seen": 1,
                "first_seen": "2025-01-15",
                "last_seen": "2025-01-15",
            }
        ]
        suggestions_table(data)
        call_args = _mock_streamlit["tables"].dataframe.call_args
        df = call_args[0][0] if call_args[0] else call_args[1]["data"]
        assert "Öneri" in df.columns
        assert "Duygu" in df.columns
        assert "Skor" in df.columns

    def test_emoji_in_sentiment_column(self, _mock_streamlit):

        from suggestguard.ui.components.tables import suggestions_table

        data = [
            {
                "text": "t",
                "sentiment": "negative",
                "sentiment_score": -0.9,
                "category": None,
                "position": 1,
                "times_seen": 1,
                "first_seen": "2025-01-15",
                "last_seen": "2025-01-15",
            }
        ]
        suggestions_table(data)
        df = _mock_streamlit["tables"].dataframe.call_args[0][0]
        assert "🔴" in df["Duygu"].iloc[0]


class TestDiffTable:
    def test_tabs_created(self, _mock_streamlit):
        from suggestguard.ui.components.tables import diff_table

        diff = {
            "new_suggestions": [{"text": "new one"}],
            "disappeared": [],
            "position_changes": [],
        }
        diff_table(diff)
        _mock_streamlit["tables"].tabs.assert_called_once()

    def test_tab_labels_contain_counts(self, _mock_streamlit):
        from suggestguard.ui.components.tables import diff_table

        diff = {
            "new_suggestions": [{"text": "a"}, {"text": "b"}],
            "disappeared": [{"text": "c"}],
            "position_changes": [{"text": "d", "old_position": 1, "new_position": 3}],
        }
        diff_table(diff)
        tab_labels = _mock_streamlit["tables"].tabs.call_args[0][0]
        assert "(2)" in tab_labels[0]  # Yeni
        assert "(1)" in tab_labels[1]  # Kaybolan
        assert "(1)" in tab_labels[2]  # Değişen


class TestCampaignComparisonTable:
    def test_empty_comparison(self, _mock_streamlit):
        from suggestguard.ui.components.tables import campaign_comparison_table

        campaign_comparison_table({})
        _mock_streamlit["tables"].info.assert_called_once()

    def test_renders_with_data(self, _mock_streamlit):
        from suggestguard.ui.components.tables import campaign_comparison_table

        comparison = {
            "campaign": {
                "name": "SEO Kampanyası",
                "started_at": "2025-01-01",
                "ended_at": "2025-02-01",
            },
            "before": {"total": 50, "negative": 20, "positive": 20, "neutral": 10},
            "during": {"total": 60, "negative": 10, "positive": 35, "neutral": 15},
        }
        campaign_comparison_table(comparison)
        _mock_streamlit["tables"].dataframe.assert_called_once()

    def test_negative_ratio_row(self, _mock_streamlit):
        from suggestguard.ui.components.tables import campaign_comparison_table

        comparison = {
            "campaign": {"name": "Test", "started_at": "2025-01-01", "ended_at": None},
            "before": {"total": 100, "negative": 40, "positive": 40, "neutral": 20},
            "during": {"total": 100, "negative": 20, "positive": 50, "neutral": 30},
        }
        campaign_comparison_table(comparison)
        df = _mock_streamlit["tables"].dataframe.call_args[0][0]
        ratio_row = df[df["Metrik"] == "Negatif Oranı (%)"]
        assert len(ratio_row) == 1
        assert "%40.0" in ratio_row["Önce"].values[0]
        assert "%20.0" in ratio_row["Kampanya Sırasında"].values[0]


# ══════════════════════════════════════════════════════════════════════
# tables.py internal helpers
# ══════════════════════════════════════════════════════════════════════


class TestPositionDelta:
    def test_up(self):
        from suggestguard.ui.components.tables import _position_delta

        assert _position_delta(5, 2) == "↑ 3"

    def test_down(self):
        from suggestguard.ui.components.tables import _position_delta

        assert _position_delta(2, 5) == "↓ 3"

    def test_same(self):
        from suggestguard.ui.components.tables import _position_delta

        assert _position_delta(3, 3) == "—"

    def test_none_old(self):
        from suggestguard.ui.components.tables import _position_delta

        assert _position_delta(None, 3) == "—"

    def test_none_new(self):
        from suggestguard.ui.components.tables import _position_delta

        assert _position_delta(3, None) == "—"
