"""Tarama — run and review autocomplete scans."""

from __future__ import annotations

import asyncio
import csv
import io
import time

import streamlit as st

from suggestguard.config import SuggestGuardConfig, get_db
from suggestguard.scanner import ScanEngine
from suggestguard.ui.components.cards import metric_card
from suggestguard.ui.components.tables import suggestions_table

# ── page setup ───────────────────────────────────────────────────────

st.header("🔍 Tarama")
st.caption("Google Autocomplete önerilerini tarayın ve analiz edin.")

db = get_db()
brands = db.list_brands(active_only=True)

# ── guard: no brands ─────────────────────────────────────────────────

if not brands:
    st.warning("Henüz aktif marka yok. Tarama başlatmak için önce bir marka ekleyin.")
    st.page_link("app.py", label="← Ana Sayfa", use_container_width=False)
    st.stop()

# ── scan configuration ───────────────────────────────────────────────

st.subheader("Tarama Ayarları")

brand_names = [b["name"] for b in brands]
brand_map = {b["name"]: b for b in brands}

scan_all = st.checkbox("Tüm Markaları Tara", value=False)

if scan_all:
    selected_brands = brands
    st.info(f"{len(brands)} marka taranacak.")
else:
    selected_name = st.selectbox("Marka Seçin", brand_names, index=0)
    selected_brands = [brand_map[selected_name]]

# ── estimate ─────────────────────────────────────────────────────────

config = SuggestGuardConfig()
config.init_config()
engine = ScanEngine(db, config)

total_queries = 0
total_seconds = 0.0
for brand in selected_brands:
    est = engine.get_scan_estimate(brand)
    total_queries += est["total_queries"]
    total_seconds += est["estimated_seconds"]

minutes = total_seconds / 60

with st.container(border=True):
    e1, e2, e3 = st.columns(3)
    with e1:
        st.metric("Sorgu Sayısı", f"~{total_queries}")
    with e2:
        if minutes >= 1:
            st.metric("Tahmini Süre", f"~{minutes:.1f} dk")
        else:
            st.metric("Tahmini Süre", f"~{total_seconds:.0f} sn")
    with e3:
        st.metric("Marka Sayısı", len(selected_brands))

# ── scan button ──────────────────────────────────────────────────────

if st.button("🔍 Taramayı Başlat", type="primary", use_container_width=True):
    # ── run scan ─────────────────────────────────────────────────
    start_time = time.time()
    reports: list[dict] = []
    errors: list[str] = []

    progress_bar = st.progress(0, text="Tarama başlatılıyor...")
    status = st.status("Tarama devam ediyor...", expanded=True)

    brand_progress: dict[int, int] = {}
    completed_brands = 0

    for brand_idx, brand in enumerate(selected_brands):
        brand_name = brand["name"]

        status.write(f"**{brand_name}** taranıyor...")

        # progress callback updates bar + status text
        def make_callback(b_name: str, b_idx: int):
            def _progress(current: int, total: int, query: str) -> None:
                brand_frac = b_idx / len(selected_brands)
                within_frac = current / total if total > 0 else 0
                overall = brand_frac + within_frac / len(selected_brands)
                progress_bar.progress(
                    min(overall, 0.99),
                    text=f"{b_name}: {current}/{total} — {query}",
                )

            return _progress

        callback = make_callback(brand_name, brand_idx)

        try:
            report = asyncio.run(engine.scan_brand(brand, progress_callback=callback))
            reports.append(report)
            status.write(f"  {brand_name}: {report['total_suggestions']} öneri bulundu.")
        except Exception as exc:
            error_msg = str(exc)
            errors.append(f"{brand_name}: {error_msg}")
            reports.append(
                {
                    "brand_id": brand["id"],
                    "brand_name": brand_name,
                    "error": True,
                    "error_message": error_msg,
                }
            )
            status.write(f"  {brand_name}: HATA — {error_msg}")

        completed_brands += 1

    elapsed = time.time() - start_time
    progress_bar.progress(1.0, text="Tarama tamamlandı!")
    status.update(label="Tarama tamamlandı!", state="complete", expanded=False)

    # ── store results in session state ───────────────────────────
    st.session_state["scan_reports"] = reports
    st.session_state["scan_errors"] = errors
    st.session_state["scan_elapsed"] = elapsed

# ── display results ──────────────────────────────────────────────────

if "scan_reports" in st.session_state:
    reports = st.session_state["scan_reports"]
    errors = st.session_state.get("scan_errors", [])
    elapsed = st.session_state.get("scan_elapsed", 0)

    st.divider()
    st.subheader("Tarama Sonuçları")

    # ── error alerts ─────────────────────────────────────────────
    if errors:
        for err in errors:
            st.error(f"Hata: {err}")

    # ── summary cards per brand ──────────────────────────────────
    successful = [r for r in reports if not r.get("error")]

    if not successful:
        st.error("Tüm taramalar başarısız oldu. Lütfen bağlantınızı kontrol edin.")
        st.stop()

    for report in successful:
        brand_name = report["brand_name"]
        summary = report.get("summary", {})
        diff_summary = report.get("diff", {})

        st.markdown(f"### {brand_name}")

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            metric_card("Sorgu", report.get("total_queries", 0))
        with c2:
            metric_card("Öneri", report.get("total_suggestions", 0))
        with c3:
            metric_card(
                "Negatif",
                summary.get("negative", 0),
                delta_color="inverse",
            )
        with c4:
            metric_card("Pozitif", summary.get("positive", 0))
        with c5:
            metric_card("Süre", f"{elapsed:.1f}s")

        # ── new negatives alert ──────────────────────────────────
        new_neg = report.get("new_negatives", 0)
        if new_neg > 0:
            st.warning(
                f"{new_neg} yeni negatif öneri tespit edildi! Dashboard'dan detaylı inceleyin."
            )

        # ── tabs: all suggestions | diff | negatives ─────────────
        brand_id = report["brand_id"]
        all_sugg = db.get_suggestions_for_brand(brand_id)
        new_sugg = db.get_new_suggestions(brand_id, since_days=1)
        disappeared = db.get_disappeared_suggestions(brand_id, not_seen_days=1)
        negatives = [s for s in all_sugg if s.get("sentiment") == "negative"]

        tab_all, tab_new, tab_gone, tab_neg = st.tabs(
            [
                f"Tüm Öneriler ({len(all_sugg)})",
                f"🆕 Yeni ({len(new_sugg)})",
                f"👋 Kaybolan ({len(disappeared)})",
                f"🔴 Negatifler ({len(negatives)})",
            ]
        )

        with tab_all:
            if all_sugg:
                suggestions_table(all_sugg)
            else:
                st.info("Henüz öneri yok.")

        with tab_new:
            if new_sugg:
                suggestions_table(new_sugg)
            else:
                st.info("Yeni öneri tespit edilmedi.")

        with tab_gone:
            if disappeared:
                suggestions_table(disappeared)
            else:
                st.info("Kaybolan öneri yok.")

        with tab_neg:
            if negatives:
                suggestions_table(negatives)
            else:
                st.success("Negatif öneri yok!")

        # ── CSV download ─────────────────────────────────────────
        if all_sugg:
            csv_buffer = io.StringIO()
            writer = csv.DictWriter(
                csv_buffer,
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
            writer.writerows(all_sugg)

            st.download_button(
                label="📥 CSV İndir",
                data=csv_buffer.getvalue(),
                file_name=f"{brand_name}_oneriler.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.divider()
