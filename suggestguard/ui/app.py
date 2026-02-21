"""SuggestGuard — Streamlit dashboard entry point."""

from __future__ import annotations

import streamlit as st

from suggestguard.config import get_db
from suggestguard.ui.components.cards import brand_health_card
from suggestguard.ui.demo_data import seed_demo_data

# ── page config (must be the first st call) ──────────────────────────

st.set_page_config(
    page_title="SuggestGuard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── database ─────────────────────────────────────────────────────────

db = get_db()

# ── sidebar ──────────────────────────────────────────────────────────

with st.sidebar:
    st.image(
        "https://img.icons8.com/fluency/96/shield.png",
        width=64,
    )
    st.title("SuggestGuard")
    st.caption("v0.1.0")
    st.divider()

    # last scan info
    brands = db.list_brands(active_only=True)
    if brands:
        latest_scans = []
        for b in brands:
            stats = db.get_brand_stats(b["id"])
            if stats.get("last_scan"):
                latest_scans.append(stats["last_scan"])
        if latest_scans:
            st.caption(f"Son tarama: {max(latest_scans)}")
        else:
            st.caption("Son tarama: —")
        st.caption(f"Aktif marka: {len(brands)}")
    else:
        st.caption("Henüz marka eklenmedi.")

    st.divider()

    # Demo data seeder
    if st.button("🎲 Demo Veri Oluştur", use_container_width=True):
        with st.spinner("Demo veri oluşturuluyor..."):
            seed_demo_data(db)
        st.success("Demo veri oluşturuldu!")
        st.rerun()

# ── main content ─────────────────────────────────────────────────────

st.title("🛡️ SuggestGuard")
st.caption("Google Autocomplete İtibar Yönetimi")

brands = db.list_brands(active_only=True)

if not brands:
    # ── no brands → setup guidance ───────────────────────────────
    st.divider()
    st.info(
        "**Hoş geldiniz!** Henüz hiç marka eklenmemiş.\n\n"
        "Başlamak için aşağıdaki seçeneklerden birini kullanın:"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        with st.container(border=True):
            st.subheader("🏷️ Marka Ekle")
            st.write(
                "İzlemek istediğiniz markaları ekleyin. "
                "Her marka için anahtar kelimeler belirleyin."
            )
            st.page_link(
                "pages/4_🏷️_Markalar.py",
                label="Markalar Sayfası →",
                use_container_width=True,
            )

    with c2:
        with st.container(border=True):
            st.subheader("⚙️ Ayarları Yapın")
            st.write("Bildirim kanallarını (Telegram, Slack) ve tarama ayarlarını yapılandırın.")
            st.page_link(
                "pages/6_⚙️_Ayarlar.py",
                label="Ayarlar Sayfası →",
                use_container_width=True,
            )

    with c3:
        with st.container(border=True):
            st.subheader("🎲 Demo Veri")
            st.write("Dashboard'u hemen keşfetmek için demo veri oluşturun.")
            if st.button("Demo Veri Oluştur", key="hero_demo"):
                with st.spinner("Demo veri oluşturuluyor..."):
                    seed_demo_data(db)
                st.success("Demo veri oluşturuldu!")
                st.rerun()

else:
    # ── brands exist → welcome + quick cards ─────────────────────
    st.divider()

    c1, c2, c3 = st.columns(3)

    with c1:
        with st.container(border=True):
            st.subheader("📊 Dashboard")
            st.write("Marka itibar metriklerini ve trendleri görüntüleyin.")
            st.page_link(
                "pages/1_📊_Dashboard.py",
                label="Dashboard →",
                use_container_width=True,
            )

    with c2:
        with st.container(border=True):
            st.subheader("🔍 Tarama Başlat")
            st.write("Seçili markalar için yeni bir autocomplete taraması başlatın.")
            st.page_link(
                "pages/2_🔍_Tarama.py",
                label="Tarama →",
                use_container_width=True,
            )

    with c3:
        with st.container(border=True):
            st.subheader("📈 Raporlar")
            st.write("Detaylı analiz raporları ve trend grafikleri inceleyin.")
            st.page_link(
                "pages/3_📈_Raporlar.py",
                label="Raporlar →",
                use_container_width=True,
            )

    # ── quick brand overview ─────────────────────────────────────
    st.divider()
    st.subheader("Marka Özeti")

    for brand in brands:
        stats = db.get_brand_stats(brand["id"])
        brand_health_card(brand["name"], stats)
