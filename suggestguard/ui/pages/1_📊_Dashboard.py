"""Dashboard — overview of brand reputation metrics."""

from __future__ import annotations

import streamlit as st

from suggestguard.config import get_db
from suggestguard.ui.components.cards import metric_card
from suggestguard.ui.components.charts import (
    category_bar_chart,
    negative_trend_line,
    sentiment_pie_chart,
)
from suggestguard.ui.components.filters import (
    SENTIMENT_OPTIONS,
    SENTIMENT_VALUE_MAP,
    brand_selector,
    require_brands,
)
from suggestguard.ui.components.tables import suggestions_table

# ── page setup ───────────────────────────────────────────────────────

st.header("📊 Dashboard")

db = get_db()
brands = require_brands(db)

# ── brand selector ───────────────────────────────────────────────────

brand = brand_selector(brands)
brand_id = brand["id"]
selected_name = brand["name"]

# ── fetch data ───────────────────────────────────────────────────────

stats = db.get_brand_stats(brand_id)
daily_data = db.get_daily_sentiment_counts(brand_id, days=30)
all_suggestions = db.get_suggestions_for_brand(brand_id)
new_7d = db.get_new_suggestions(brand_id, since_days=7)
disappeared = db.get_disappeared_suggestions(brand_id, not_seen_days=7)
top_negatives = db.get_top_negative_suggestions(brand_id, limit=20)

# ── guard: no data ───────────────────────────────────────────────────

if stats["total_suggestions"] == 0:
    st.warning(
        f"**{selected_name}** için henüz tarama verisi yok. Tarama sayfasından bir tarama başlatın."
    )
    st.page_link(
        "pages/2_🔍_Tarama.py",
        label="🔍 Tarama Başlat →",
        use_container_width=False,
    )
    st.stop()

# ── summary metrics ──────────────────────────────────────────────────

st.subheader("Özet")

neg_ratio = stats.get("negative_ratio", 0.0)
health_score = round(100 - neg_ratio * 100, 1)

c1, c2, c3, c4 = st.columns(4)

with c1:
    metric_card("Toplam Öneri", stats["total_suggestions"])
with c2:
    metric_card(
        "Negatif",
        stats["negative_count"],
        delta=f"{stats.get('new_last_7d', 0)} yeni (7g)",
        delta_color="inverse",
    )
with c3:
    metric_card("Pozitif", stats["positive_count"])
with c4:
    if health_score >= 70:
        delta_color = "normal"
    elif health_score >= 40:
        delta_color = "off"
    else:
        delta_color = "inverse"
    metric_card("Sağlık Skoru", health_score, delta_color=delta_color)

# ── charts row: negative trend + sentiment pie ───────────────────────

st.divider()
st.subheader("Grafikler")

col_left, col_right = st.columns([3, 2])

with col_left:
    if daily_data:
        negative_trend_line(daily_data)
    else:
        st.info("Henüz günlük veri yok.")

with col_right:
    summary_for_pie = {
        "negative": stats["negative_count"],
        "positive": stats["positive_count"],
        "neutral": stats["neutral_count"],
    }
    sentiment_pie_chart(summary_for_pie)

# ── category bar chart ───────────────────────────────────────────────

# build category counts from top negatives
categories: dict[str, int] = {}
for s in all_suggestions:
    cat = s.get("category")
    if cat and s.get("sentiment") == "negative":
        categories[cat] = categories.get(cat, 0) + 1

if categories:
    category_bar_chart(categories)

# ── active suggestions table ─────────────────────────────────────────

st.divider()
st.subheader("Aktif Öneriler")

# filters
filter_col1, filter_col2 = st.columns([1, 3])

with filter_col1:
    sentiment_filter = st.selectbox(
        "Duygu Filtresi",
        SENTIMENT_OPTIONS,
        index=0,
    )

with filter_col2:
    search_query = st.text_input("Ara", placeholder="Öneri metni ara...")

# apply filters
filtered = all_suggestions
sentiment_value = SENTIMENT_VALUE_MAP.get(sentiment_filter)
if sentiment_value:
    filtered = [s for s in filtered if s.get("sentiment") == sentiment_value]

if search_query:
    q = search_query.lower()
    filtered = [s for s in filtered if q in s.get("text", "").lower()]

suggestions_table(filtered)

# ── tabbed section: new / disappeared / persistent negative ──────────

st.divider()

tab_new, tab_gone, tab_persistent = st.tabs(
    [
        f"🆕 Yeni (7 gün) ({len(new_7d)})",
        f"👋 Kaybolan ({len(disappeared)})",
        f"⚠️ Sürekli Negatif ({len(top_negatives)})",
    ]
)

with tab_new:
    if new_7d:
        suggestions_table(new_7d)
    else:
        st.info("Son 7 günde yeni öneri tespit edilmedi.")

with tab_gone:
    if disappeared:
        suggestions_table(disappeared)
    else:
        st.info("Kaybolan öneri yok.")

with tab_persistent:
    if top_negatives:
        suggestions_table(top_negatives)
    else:
        st.success("Sürekli negatif öneri yok — harika!")
