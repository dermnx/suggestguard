"""Kampanyalar — reputation campaigns and action plans."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from suggestguard.config import get_db
from suggestguard.ui.components import format_date

# ── page setup ───────────────────────────────────────────────────────

st.header("📢 Kampanyalar")
st.caption("İtibar kampanyalarını başlatın, takip edin ve sonuçlarını analiz edin.")

db = get_db()
brands = db.list_brands(active_only=True)

# ── chart colours ─────────────────────────────────────────────────────

COLOR_NEGATIVE = "#EF4444"
COLOR_POSITIVE = "#22C55E"
COLOR_NEUTRAL = "#6B7280"
COLOR_TEXT = "#E2E8F0"
COLOR_PRIMARY = "#3B82F6"

# ======================================================================
# 1. Yeni Kampanya Başlat
# ======================================================================

st.subheader("Yeni Kampanya Başlat")

if not brands:
    st.info("Önce bir marka ekleyin (🏷️ Markalar sayfasından).")
else:
    with st.form("new_campaign_form", clear_on_submit=True):
        brand_options = {b["name"]: b["id"] for b in brands}

        nc1, nc2 = st.columns([2, 3])
        with nc1:
            selected_brand = st.selectbox("Marka", list(brand_options.keys()))
        with nc2:
            campaign_name = st.text_input(
                "Kampanya Adı",
                placeholder="Örn: SEO İyileştirme Kampanyası",
            )

        campaign_notes = st.text_area(
            "Notlar (opsiyonel)",
            placeholder="Kampanya hakkında açıklama...",
            height=80,
        )

        if st.form_submit_button("🚀 Kampanyayı Başlat", type="primary", use_container_width=True):
            if not campaign_name.strip():
                st.error("Kampanya adı boş olamaz.")
            else:
                brand_id = brand_options[selected_brand]
                cid = db.add_campaign(
                    brand_id=brand_id,
                    name=campaign_name.strip(),
                    notes=campaign_notes.strip() or None,
                )
                st.success(f"**{campaign_name.strip()}** kampanyası başlatıldı! (ID: {cid})")
                st.balloons()
                st.rerun()

# ======================================================================
# 2. Aktif Kampanyalar
# ======================================================================

st.divider()
st.subheader("Aktif Kampanyalar")

all_campaigns = db.list_campaigns()
brand_map = {b["id"]: b["name"] for b in db.list_brands(active_only=False)}

active_campaigns = [c for c in all_campaigns if c.get("ended_at") is None]
completed_campaigns = [c for c in all_campaigns if c.get("ended_at") is not None]

if not active_campaigns:
    st.info("Şu anda aktif kampanya yok. Yukarıdan yeni bir kampanya başlatın.")
else:
    for camp in active_campaigns:
        camp_id = camp["id"]
        brand_name = brand_map.get(camp["brand_id"], "?")

        with st.container(border=True):
            h_left, h_right = st.columns([4, 1])
            with h_left:
                st.markdown(f"### 🟢 {camp['name']}")
                st.caption(
                    f"Marka: **{brand_name}** | Başlangıç: {format_date(camp['started_at'])}"
                )
            with h_right:
                st.caption(f"ID: {camp_id}")

            if camp.get("notes"):
                st.markdown(f"_{camp['notes']}_")

            # ── comparison metrics ──────────────────────────────────
            comparison = db.get_campaign_comparison(camp_id)
            if comparison:
                before = comparison["before"]
                during = comparison["during"]

                m1, m2, m3, m4 = st.columns(4)

                before_neg = before.get("negative") or 0
                during_neg = during.get("negative") or 0
                before_total = before.get("total") or 0
                during_total = during.get("total") or 0

                neg_delta = during_neg - before_neg
                with m1:
                    st.metric(
                        "Önceki Negatif",
                        before_neg,
                    )
                with m2:
                    st.metric(
                        "Kampanya Negatif",
                        during_neg,
                        delta=f"{neg_delta:+d}" if neg_delta != 0 else "0",
                        delta_color="inverse",
                    )
                with m3:
                    before_ratio = (
                        round(before_neg / before_total * 100, 1) if before_total > 0 else 0.0
                    )
                    st.metric("Önceki Negatif Oranı", f"%{before_ratio}")
                with m4:
                    during_ratio = (
                        round(during_neg / during_total * 100, 1) if during_total > 0 else 0.0
                    )
                    ratio_delta = round(during_ratio - before_ratio, 1)
                    st.metric(
                        "Kampanya Negatif Oranı",
                        f"%{during_ratio}",
                        delta=f"{ratio_delta:+.1f}%" if ratio_delta != 0 else "0%",
                        delta_color="inverse",
                    )

            # ── end campaign button ─────────────────────────────────
            if st.button(
                "🏁 Kampanyayı Bitir",
                key=f"end_{camp_id}",
                use_container_width=True,
            ):
                st.session_state[f"confirm_end_{camp_id}"] = True

            if st.session_state.get(f"confirm_end_{camp_id}"):
                st.warning(f"**{camp['name']}** kampanyası bitirilecek. Bu işlem geri alınamaz.")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button(
                        "Evet, Bitir",
                        key=f"confirm_end_yes_{camp_id}",
                        type="primary",
                    ):
                        db.end_campaign(camp_id)
                        st.session_state.pop(f"confirm_end_{camp_id}", None)
                        st.success(f"**{camp['name']}** kampanyası bitirildi!")
                        st.rerun()
                with cc2:
                    if st.button("İptal", key=f"confirm_end_no_{camp_id}"):
                        st.session_state.pop(f"confirm_end_{camp_id}", None)
                        st.rerun()

# ======================================================================
# 3. Tamamlanan Kampanyalar & Raporlar
# ======================================================================

st.divider()
st.subheader("Tamamlanan Kampanyalar")

if not completed_campaigns:
    st.info("Henüz tamamlanmış kampanya yok.")
else:
    for camp in completed_campaigns:
        camp_id = camp["id"]
        brand_name = brand_map.get(camp["brand_id"], "?")

        with st.container(border=True):
            st.markdown(f"### ✅ {camp['name']}")
            st.caption(
                f"Marka: **{brand_name}** | "
                f"{format_date(camp['started_at'])} → "
                f"{format_date(camp['ended_at'])}"
            )

            if camp.get("notes"):
                st.markdown(f"_{camp['notes']}_")

            # ── detailed report expander ────────────────────────────
            with st.expander("📊 Kampanya Raporu"):
                comparison = db.get_campaign_comparison(camp_id)
                if not comparison:
                    st.warning("Rapor verisi bulunamadı.")
                    continue

                campaign_data = comparison["campaign"]
                before = comparison["before"]
                during = comparison["during"]

                before_neg = before.get("negative") or 0
                during_neg = during.get("negative") or 0
                before_total = before.get("total") or 0
                during_total = during.get("total") or 0

                # ── before / during metric cards ────────────────────
                st.markdown("#### Önce / Sonra Karşılaştırma")

                rm1, rm2, rm3, rm4 = st.columns(4)

                neg_change = during_neg - before_neg
                neg_pct = round(neg_change / before_neg * 100, 1) if before_neg > 0 else 0.0

                with rm1:
                    st.metric("Önceki Negatif", before_neg)
                with rm2:
                    st.metric(
                        "Kampanya Negatif",
                        during_neg,
                        delta=f"{neg_change:+d}" if neg_change != 0 else "0",
                        delta_color="inverse",
                    )
                with rm3:
                    st.metric("Önceki Toplam", before_total)
                with rm4:
                    total_change = (during_total or 0) - before_total
                    st.metric(
                        "Kampanya Toplam",
                        during_total or 0,
                        delta=f"{total_change:+d}" if total_change != 0 else "0",
                    )

                # ── ratio comparison ────────────────────────────────
                before_ratio = (
                    round(before_neg / before_total * 100, 1) if before_total > 0 else 0.0
                )
                during_ratio = (
                    round(during_neg / during_total * 100, 1) if during_total > 0 else 0.0
                )
                ratio_delta = round(during_ratio - before_ratio, 1)

                rr1, rr2, rr3 = st.columns(3)
                with rr1:
                    st.metric("Önceki Negatif Oranı", f"%{before_ratio}")
                with rr2:
                    st.metric(
                        "Kampanya Negatif Oranı",
                        f"%{during_ratio}",
                        delta=f"{ratio_delta:+.1f}%" if ratio_delta != 0 else "0%",
                        delta_color="inverse",
                    )
                with rr3:
                    if ratio_delta < 0:
                        verdict = "🟢 İyileşme"
                    elif ratio_delta > 0:
                        verdict = "🔴 Kötüleşme"
                    else:
                        verdict = "⚪ Değişim Yok"
                    st.metric("Sonuç", verdict)

                # ── comparison table ────────────────────────────────
                from suggestguard.ui.components.tables import (
                    campaign_comparison_table,
                )

                campaign_comparison_table(comparison)

                # ── negative ratio chart with vertical lines ────────
                st.markdown("#### Negatif Oran Grafiği")

                started_at = campaign_data["started_at"]
                ended_at = campaign_data.get("ended_at")

                daily = db.get_daily_sentiment_counts(camp["brand_id"], days=60)

                if daily:
                    dates = [d["date"] for d in daily]
                    ratios = [
                        round(
                            (d.get("negative") or 0) / d["total"] * 100,
                            1,
                        )
                        if d.get("total", 0) > 0
                        else 0.0
                        for d in daily
                    ]

                    fig = go.Figure()

                    fig.add_trace(
                        go.Scatter(
                            x=dates,
                            y=ratios,
                            mode="lines+markers",
                            name="Negatif Oranı (%)",
                            line=dict(color=COLOR_NEGATIVE, width=2),
                            marker=dict(size=5),
                        )
                    )

                    # vertical line: campaign start
                    start_date = started_at[:10]
                    fig.add_shape(
                        type="line",
                        x0=start_date,
                        x1=start_date,
                        y0=0,
                        y1=1,
                        yref="paper",
                        line=dict(color=COLOR_POSITIVE, width=2, dash="dash"),
                    )
                    fig.add_annotation(
                        x=start_date,
                        y=1,
                        yref="paper",
                        text="Başlangıç",
                        showarrow=False,
                        font=dict(color=COLOR_POSITIVE),
                        yshift=10,
                    )

                    # vertical line: campaign end
                    if ended_at:
                        end_date = ended_at[:10]
                        fig.add_shape(
                            type="line",
                            x0=end_date,
                            x1=end_date,
                            y0=0,
                            y1=1,
                            yref="paper",
                            line=dict(color=COLOR_PRIMARY, width=2, dash="dash"),
                        )
                        fig.add_annotation(
                            x=end_date,
                            y=1,
                            yref="paper",
                            text="Bitiş",
                            showarrow=False,
                            font=dict(color=COLOR_PRIMARY),
                            yshift=10,
                        )

                    fig.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color=COLOR_TEXT),
                        margin=dict(l=40, r=20, t=40, b=40),
                        xaxis=dict(title="Tarih"),
                        yaxis=dict(
                            title="Negatif Oranı (%)",
                            rangemode="tozero",
                        ),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Grafik için yeterli veri yok.")

                # ── disappeared / new negatives ─────────────────────
                st.markdown("#### Kampanya Süresince Değişimler")

                brand_id = camp["brand_id"]

                # negatives that existed before but disappeared during
                disappeared_rows = db.conn.execute(
                    """SELECT * FROM suggestions
                       WHERE brand_id = ?
                         AND sentiment = 'negative'
                         AND first_seen < ?
                         AND last_seen < ?
                       ORDER BY text""",
                    (brand_id, started_at, started_at),
                ).fetchall()

                # new negatives that appeared during the campaign
                end_ts = ended_at or started_at
                new_neg_rows = db.conn.execute(
                    """SELECT * FROM suggestions
                       WHERE brand_id = ?
                         AND sentiment = 'negative'
                         AND first_seen >= ?
                         AND first_seen <= ?
                       ORDER BY first_seen DESC""",
                    (brand_id, started_at, end_ts),
                ).fetchall()

                ch1, ch2 = st.columns(2)

                with ch1:
                    st.markdown("##### ✅ Kaybolan Negatifler")
                    if disappeared_rows:
                        for row in disappeared_rows:
                            st.markdown(f"- ~~{row['text']}~~")
                    else:
                        st.caption("Kaybolan negatif öneri yok.")

                with ch2:
                    st.markdown("##### ❌ Yeni Negatifler")
                    if new_neg_rows:
                        for row in new_neg_rows:
                            st.markdown(f"- {row['text']}")
                    else:
                        st.caption("Yeni negatif öneri yok.")

# ======================================================================
# 4. Tüm Kampanyalar Özeti
# ======================================================================

st.divider()
st.subheader("Kampanya İstatistikleri")

total_campaigns = len(all_campaigns)
active_count = len(active_campaigns)
completed_count = len(completed_campaigns)

s1, s2, s3 = st.columns(3)
with s1:
    st.metric("Toplam Kampanya", total_campaigns)
with s2:
    st.metric("Aktif", active_count)
with s3:
    st.metric("Tamamlanan", completed_count)
