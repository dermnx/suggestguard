"""Raporlar — historical reports and trend analysis."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

import streamlit as st

from suggestguard.analyzers.diff import DiffAnalyzer
from suggestguard.config import get_db
from suggestguard.ui.components.cards import metric_card
from suggestguard.ui.components.charts import (
    category_bar_chart,
    negative_trend_line,
    sentiment_pie_chart,
    sentiment_stacked_bar,
)
from suggestguard.ui.components.tables import suggestions_table

# ── page setup ───────────────────────────────────────────────────────

st.header("📈 Raporlar")
st.caption("Detaylı analiz raporları, trend grafikleri ve dışa aktarım.")

db = get_db()
brands = db.list_brands(active_only=True)

# ── guard ────────────────────────────────────────────────────────────

if not brands:
    st.info("Henüz marka eklenmemiş.")
    st.page_link("app.py", label="← Ana Sayfa", use_container_width=False)
    st.stop()

# ── filters ──────────────────────────────────────────────────────────

st.subheader("Filtreler")

f1, f2, f3 = st.columns([2, 2, 1])

with f1:
    brand_names = [b["name"] for b in brands]
    brand_map = {b["name"]: b for b in brands}
    selected_name = st.selectbox("Marka", brand_names, index=0)
    brand = brand_map[selected_name]
    brand_id = brand["id"]

with f2:
    date_range = st.selectbox(
        "Tarih Aralığı",
        ["Son 7 gün", "Son 14 gün", "Son 30 gün", "Son 90 gün", "Tümü"],
        index=2,
    )
    RANGE_MAP = {
        "Son 7 gün": 7,
        "Son 14 gün": 14,
        "Son 30 gün": 30,
        "Son 90 gün": 90,
        "Tümü": None,
    }
    days = RANGE_MAP[date_range]

with f3:
    sentiment_filter = st.selectbox(
        "Duygu",
        ["Tümü", "Negatif", "Pozitif", "Nötr"],
        index=0,
    )
    SENTIMENT_MAP = {
        "Tümü": None,
        "Negatif": "negative",
        "Pozitif": "positive",
        "Nötr": "neutral",
    }
    sentiment_value = SENTIMENT_MAP[sentiment_filter]

# ── fetch data ───────────────────────────────────────────────────────

stats = db.get_brand_stats(brand_id)
daily_data = db.get_daily_sentiment_counts(brand_id, days=days or 365)
all_suggestions = db.get_suggestions_for_brand(brand_id, days=days, sentiment=sentiment_value)
trends = DiffAnalyzer.detect_trends(brand_id, db, days=days or 365)

if stats["total_suggestions"] == 0:
    st.warning(f"**{selected_name}** için henüz veri yok.")
    st.stop()

# ── trend indicator ──────────────────────────────────────────────────

st.divider()
st.subheader("Genel Bakış")

# compute trend from daily data
if len(daily_data) >= 2:
    first_half = daily_data[: len(daily_data) // 2]
    second_half = daily_data[len(daily_data) // 2 :]
    avg_first = sum(d.get("negative", 0) for d in first_half) / len(first_half)
    avg_second = sum(d.get("negative", 0) for d in second_half) / len(second_half)

    if avg_second > avg_first * 1.1:
        trend_text = "Negatifler artıyor"
        trend_icon = "↗️"
        trend_delta = f"+{avg_second - avg_first:.1f}/gün"
        trend_color = "inverse"
    elif avg_second < avg_first * 0.9:
        trend_text = "Negatifler azalıyor"
        trend_icon = "↘️"
        trend_delta = f"{avg_second - avg_first:.1f}/gün"
        trend_color = "normal"
    else:
        trend_text = "Negatifler sabit"
        trend_icon = "➡️"
        trend_delta = "değişim yok"
        trend_color = "off"
else:
    trend_text = "Yeterli veri yok"
    trend_icon = "❓"
    trend_delta = None
    trend_color = "off"

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    metric_card("Toplam Öneri", len(all_suggestions))
with c2:
    neg_count = sum(1 for s in all_suggestions if s.get("sentiment") == "negative")
    metric_card("Negatif", neg_count, delta_color="inverse")
with c3:
    pos_count = sum(1 for s in all_suggestions if s.get("sentiment") == "positive")
    metric_card("Pozitif", pos_count)
with c4:
    neg_ratio = stats.get("negative_ratio", 0.0)
    health = round(100 - neg_ratio * 100, 1)
    metric_card("Sağlık Skoru", health)
with c5:
    metric_card(f"{trend_icon} Trend", trend_text, delta=trend_delta, delta_color=trend_color)

# ── time series charts ───────────────────────────────────────────────

st.divider()
st.subheader("Zaman Serisi Grafikleri")

chart_tab1, chart_tab2 = st.tabs(["📉 Negatif Trend", "📊 Duygu Dağılımı (Yığılmış)"])

with chart_tab1:
    if daily_data:
        negative_trend_line(daily_data)
    else:
        st.info("Günlük veri yok.")

with chart_tab2:
    if daily_data:
        sentiment_stacked_bar(daily_data)
    else:
        st.info("Günlük veri yok.")

# ── sentiment pie + category bar ─────────────────────────────────────

pie_col, cat_col = st.columns(2)

with pie_col:
    summary_for_pie = {
        "negative": stats["negative_count"],
        "positive": stats["positive_count"],
        "neutral": stats["neutral_count"],
    }
    sentiment_pie_chart(summary_for_pie)

with cat_col:
    categories: dict[str, int] = {}
    for s in all_suggestions:
        cat = s.get("category")
        if cat and s.get("sentiment") == "negative":
            categories[cat] = categories.get(cat, 0) + 1
    if categories:
        category_bar_chart(categories)
    else:
        st.info("Negatif kategori verisi yok.")

# ── top 10 negative suggestions ──────────────────────────────────────

st.divider()
st.subheader("Top 10 Negatif Öneri")

top_negatives = db.get_top_negative_suggestions(brand_id, limit=10)
if top_negatives:
    suggestions_table(top_negatives)
else:
    st.success("Negatif öneri yok!")

# ── rising / declining / persistent negatives ────────────────────────

st.divider()
st.subheader("Negatif Trend Analizi")

tab_rising, tab_declining, tab_persistent = st.tabs(
    [
        f"↗️ Yükselen ({len(trends['rising_negative'])})",
        f"↘️ Düşen ({len(trends['declining_negative'])})",
        f"⚠️ Sürekli ({len(trends['persistent_negative'])})",
    ]
)

with tab_rising:
    if trends["rising_negative"]:
        st.caption("Son 7 günde yeni ortaya çıkan negatif öneriler.")
        suggestions_table(trends["rising_negative"])
    else:
        st.success("Yeni yükselen negatif öneri yok.")

with tab_declining:
    if trends["declining_negative"]:
        st.caption("Son 7 günde kaybolan negatif öneriler.")
        suggestions_table(trends["declining_negative"])
    else:
        st.info("Düşen negatif öneri yok.")

with tab_persistent:
    if trends["persistent_negative"]:
        st.caption("3+ kez görülen negatif öneriler — müdahale gerekebilir.")
        suggestions_table(trends["persistent_negative"])
    else:
        st.success("Sürekli negatif öneri yok!")

# ── HTML report generator ────────────────────────────────────────────


def _generate_html_report(
    *,
    brand_name: str,
    stats: dict,
    daily_data: list[dict],
    suggestions: list[dict],
    trends: dict,
    categories: dict[str, int],
) -> str:
    """Build a self-contained HTML report with Chart.js + Tailwind CDN."""
    neg = stats.get("negative_count", 0)
    pos = stats.get("positive_count", 0)
    neu = stats.get("neutral_count", 0)
    total = stats.get("total_suggestions", 0)
    neg_ratio = stats.get("negative_ratio", 0.0)
    health = round(100 - neg_ratio * 100, 1)

    dates_json = json.dumps([d["date"] for d in daily_data])
    neg_json = json.dumps([d.get("negative", 0) for d in daily_data])
    pos_json = json.dumps([d.get("positive", 0) for d in daily_data])
    neu_json = json.dumps([d.get("neutral", 0) for d in daily_data])

    cat_labels = json.dumps(list(categories.keys()))
    cat_values = json.dumps(list(categories.values()))

    # top negatives table rows
    top_neg = sorted(
        [s for s in suggestions if s.get("sentiment") == "negative"],
        key=lambda x: x.get("times_seen", 0),
        reverse=True,
    )[:10]
    _td = 'class="px-4 py-2 border-b border-gray-700"'
    neg_rows = "\n".join(
        f"<tr><td {_td}>{s.get('text', '')}</td>"
        f"<td {_td}>{s.get('category', '—')}</td>"
        f"<td {_td}>{s.get('times_seen', 1)}</td>"
        f"<td {_td}>{s.get('sentiment_score', 0):.2f}</td></tr>"
        for s in top_neg
    )

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SuggestGuard Rapor — {brand_name}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>@media print {{ .no-print {{ display: none; }} }}</style>
</head>
<body class="bg-gray-900 text-gray-100 p-8 max-w-5xl mx-auto">

<header class="mb-8">
  <h1 class="text-3xl font-bold">🛡️ SuggestGuard Rapor</h1>
  <p class="text-gray-400 mt-1">{brand_name} — {generated}</p>
</header>

<!-- metrics -->
<section class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
  <div class="bg-gray-800 rounded-lg p-4">
    <p class="text-sm text-gray-400">Toplam Öneri</p>
    <p class="text-2xl font-bold">{total}</p>
  </div>
  <div class="bg-gray-800 rounded-lg p-4">
    <p class="text-sm text-gray-400">Negatif</p>
    <p class="text-2xl font-bold text-red-400">{neg}</p>
  </div>
  <div class="bg-gray-800 rounded-lg p-4">
    <p class="text-sm text-gray-400">Pozitif</p>
    <p class="text-2xl font-bold text-green-400">{pos}</p>
  </div>
  <div class="bg-gray-800 rounded-lg p-4">
    <p class="text-sm text-gray-400">Sağlık Skoru</p>
    <p class="text-2xl font-bold">{health}</p>
  </div>
</section>

<!-- trend chart -->
<section class="mb-8">
  <h2 class="text-xl font-semibold mb-4">Günlük Duygu Trendi</h2>
  <div class="bg-gray-800 rounded-lg p-4">
    <canvas id="trendChart" height="100"></canvas>
  </div>
</section>

<!-- pie + category side by side -->
<section class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
  <div class="bg-gray-800 rounded-lg p-4">
    <h3 class="text-lg font-semibold mb-2">Duygu Dağılımı</h3>
    <canvas id="pieChart" height="200"></canvas>
  </div>
  <div class="bg-gray-800 rounded-lg p-4">
    <h3 class="text-lg font-semibold mb-2">Negatif Kategoriler</h3>
    <canvas id="catChart" height="200"></canvas>
  </div>
</section>

<!-- top negatives -->
<section class="mb-8">
  <h2 class="text-xl font-semibold mb-4">Top 10 Negatif Öneri</h2>
  <div class="bg-gray-800 rounded-lg overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-600">
          <th class="px-4 py-2 text-left">Öneri</th>
          <th class="px-4 py-2 text-left">Kategori</th>
          <th class="px-4 py-2 text-left">Görülme</th>
          <th class="px-4 py-2 text-left">Skor</th>
        </tr>
      </thead>
      <tbody>{neg_rows}</tbody>
    </table>
  </div>
</section>

<footer class="text-center text-gray-500 text-xs mt-12">
  SuggestGuard v0.1.0 — {generated}
</footer>

<script>
const dates = {dates_json};
const negData = {neg_json};
const posData = {pos_json};
const neuData = {neu_json};

new Chart(document.getElementById('trendChart'), {{
  type: 'line',
  data: {{
    labels: dates,
    datasets: [
      {{ label: 'Negatif', data: negData,
         borderColor: '#EF4444',
         backgroundColor: 'rgba(239,68,68,0.1)',
         fill: true }},
      {{ label: 'Pozitif', data: posData,
         borderColor: '#22C55E',
         backgroundColor: 'rgba(34,197,94,0.1)',
         fill: true }},
      {{ label: 'Nötr', data: neuData,
         borderColor: '#6B7280',
         backgroundColor: 'rgba(107,114,128,0.1)',
         fill: true }}
    ]
  }},
  options: {{
    scales: {{
      x: {{ ticks: {{ color: '#9CA3AF' }},
           grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
      y: {{ ticks: {{ color: '#9CA3AF' }},
           grid: {{ color: 'rgba(255,255,255,0.05)' }},
           beginAtZero: true }}
    }},
    plugins: {{
      legend: {{ labels: {{ color: '#E2E8F0' }} }}
    }}
  }}
}});

new Chart(document.getElementById('pieChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['Negatif', 'Pozitif', 'Nötr'],
    datasets: [{{
      data: [{neg}, {pos}, {neu}],
      backgroundColor: ['#EF4444', '#22C55E', '#6B7280']
    }}]
  }},
  options: {{
    plugins: {{
      legend: {{ labels: {{ color: '#E2E8F0' }} }}
    }}
  }}
}});

new Chart(document.getElementById('catChart'), {{
  type: 'bar',
  data: {{
    labels: {cat_labels},
    datasets: [{{
      label: 'Sayı',
      data: {cat_values},
      backgroundColor: '#EF4444'
    }}]
  }},
  options: {{
    indexAxis: 'y',
    scales: {{
      x: {{ ticks: {{ color: '#9CA3AF' }},
           grid: {{ color: 'rgba(255,255,255,0.05)' }},
           beginAtZero: true }},
      y: {{ ticks: {{ color: '#9CA3AF' }},
           grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
    }},
    plugins: {{ legend: {{ display: false }} }}
  }}
}});
</script>
</body>
</html>"""


# ── export ───────────────────────────────────────────────────────────

st.divider()
st.subheader("Dışa Aktar")

exp1, exp2, exp3 = st.columns(3)

# CSV
with exp1:
    if all_suggestions:
        csv_buf = io.StringIO()
        writer = csv.DictWriter(
            csv_buf,
            fieldnames=[
                "text",
                "sentiment",
                "sentiment_score",
                "category",
                "position",
                "times_seen",
                "first_seen",
                "last_seen",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(all_suggestions)
        st.download_button(
            "📥 CSV İndir",
            data=csv_buf.getvalue(),
            file_name=f"{selected_name}_rapor.csv",
            mime="text/csv",
            use_container_width=True,
        )

# JSON
with exp2:
    if all_suggestions:
        json_data = json.dumps(
            all_suggestions,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        st.download_button(
            "📥 JSON İndir",
            data=json_data,
            file_name=f"{selected_name}_rapor.json",
            mime="application/json",
            use_container_width=True,
        )

# HTML report
with exp3:
    if all_suggestions:
        html_report = _generate_html_report(
            brand_name=selected_name,
            stats=stats,
            daily_data=daily_data,
            suggestions=all_suggestions,
            trends=trends,
            categories=categories,
        )
        st.download_button(
            "📥 HTML Rapor",
            data=html_report,
            file_name=f"{selected_name}_rapor.html",
            mime="text/html",
            use_container_width=True,
        )
