"""Markalar — manage tracked brands and keywords."""

from __future__ import annotations

import json
import sqlite3

import streamlit as st
import yaml

from suggestguard.config import get_db
from suggestguard.ui.components import format_date

# ── page setup ───────────────────────────────────────────────────────

st.header("🏷️ Markalar")
st.caption("İzlenen markaları yönetin, yeni marka ekleyin veya düzenleyin.")

db = get_db()

# ── helpers ──────────────────────────────────────────────────────────

LANGUAGE_OPTIONS = {"Türkçe": "tr", "English": "en", "Deutsch": "de"}
COUNTRY_OPTIONS = {"Türkiye": "TR", "ABD": "US", "Almanya": "DE", "İngiltere": "GB"}

LANGUAGE_LABELS = {v: k for k, v in LANGUAGE_OPTIONS.items()}
COUNTRY_LABELS = {v: k for k, v in COUNTRY_OPTIONS.items()}


def _parse_keywords(raw: str | list) -> list[str]:
    """Parse keywords from JSON string or newline-separated text."""
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return [kw.strip() for kw in raw.strip().splitlines() if kw.strip()]


def _keywords_to_text(keywords: str | list) -> str:
    """Convert stored keywords (JSON string or list) to newline text."""
    if isinstance(keywords, str):
        try:
            keywords = json.loads(keywords)
        except (json.JSONDecodeError, TypeError):
            return keywords
    return "\n".join(keywords)


# ── new brand form ───────────────────────────────────────────────────

st.subheader("Yeni Marka Ekle")

with st.form("add_brand_form", clear_on_submit=True):
    col_name, col_lang, col_country = st.columns([3, 1, 1])

    with col_name:
        new_name = st.text_input("Marka Adı", placeholder="Örn: Trendyol")
    with col_lang:
        new_lang_label = st.selectbox("Dil", list(LANGUAGE_OPTIONS.keys()), index=0)
    with col_country:
        new_country_label = st.selectbox("Ülke", list(COUNTRY_OPTIONS.keys()), index=0)

    new_keywords_raw = st.text_area(
        "Anahtar Kelimeler (satır satır)",
        placeholder="trendyol\ntrendyol şikayet\ntrendyol güvenilir mi",
        height=120,
    )

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        new_expand_az = st.checkbox("A-Z genişletme", value=True)
    with exp_col2:
        new_expand_tr = st.checkbox("Türkçe karakter genişletme", value=True)

    submitted = st.form_submit_button("Marka Ekle", type="primary", use_container_width=True)

    if submitted:
        if not new_name.strip():
            st.error("Marka adı boş olamaz.")
        elif not new_keywords_raw.strip():
            st.error("En az bir anahtar kelime girin.")
        else:
            keywords = _parse_keywords(new_keywords_raw)
            try:
                db.add_brand(
                    name=new_name.strip(),
                    keywords=keywords,
                    language=LANGUAGE_OPTIONS[new_lang_label],
                    country=COUNTRY_OPTIONS[new_country_label],
                    expand_az=new_expand_az,
                    expand_turkish=new_expand_tr,
                )
                st.success(f"**{new_name.strip()}** başarıyla eklendi!")
                st.balloons()
                st.rerun()
            except sqlite3.IntegrityError:
                st.error(f"**{new_name.strip()}** zaten mevcut. Farklı bir isim deneyin.")

# ── YAML import ──────────────────────────────────────────────────────

with st.expander("📄 YAML ile Toplu İçe Aktar"):
    st.caption(
        "Aşağıdaki formatta YAML yapıştırın:\n\n"
        "```yaml\n"
        "- name: Marka1\n"
        "  keywords:\n"
        "    - anahtar1\n"
        "    - anahtar2\n"
        "  language: tr\n"
        "  country: TR\n"
        "```"
    )
    yaml_input = st.text_area(
        "YAML",
        height=150,
        key="yaml_import",
        label_visibility="collapsed",
    )
    if st.button("İçe Aktar", key="import_yaml"):
        if not yaml_input.strip():
            st.warning("YAML alanı boş.")
        else:
            try:
                data = yaml.safe_load(yaml_input)
                if not isinstance(data, list):
                    st.error("YAML bir liste (array) olmalı.")
                else:
                    added = 0
                    skipped = 0
                    for item in data:
                        name = item.get("name", "").strip()
                        kws = item.get("keywords", [])
                        if not name or not kws:
                            skipped += 1
                            continue
                        try:
                            db.add_brand(
                                name=name,
                                keywords=kws if isinstance(kws, list) else [kws],
                                language=item.get("language", "tr"),
                                country=item.get("country", "TR"),
                                expand_az=item.get("expand_az", True),
                                expand_turkish=item.get("expand_turkish", True),
                            )
                            added += 1
                        except sqlite3.IntegrityError:
                            skipped += 1
                    st.success(f"{added} marka eklendi, {skipped} atlandı.")
                    if added > 0:
                        st.rerun()
            except yaml.YAMLError as exc:
                st.error(f"YAML ayrıştırma hatası: {exc}")

# ── brand list ───────────────────────────────────────────────────────

st.divider()
st.subheader("Marka Listesi")

# toggle to show inactive
show_inactive = st.checkbox("Pasif markaları da göster", value=False)
brands = db.list_brands(active_only=not show_inactive)

if not brands:
    st.info("Henüz marka eklenmemiş. Yukarıdaki formu kullanarak marka ekleyin.")
    st.stop()

# quick action row
action_col1, action_col2 = st.columns([1, 3])
with action_col1:
    st.page_link(
        "pages/2_🔍_Tarama.py",
        label="🔍 Tüm Markaları Tara",
        use_container_width=True,
    )

st.caption(f"Toplam: {len(brands)} marka")

# ── brand cards grid ─────────────────────────────────────────────────

for brand in brands:
    brand_id = brand["id"]
    brand_name = brand["name"]
    keywords = _parse_keywords(brand.get("keywords", "[]"))
    language = brand.get("language", "tr")
    country = brand.get("country", "TR")
    is_active = bool(brand.get("active", 1))

    stats = db.get_brand_stats(brand_id)
    neg_ratio = stats.get("negative_ratio", 0.0)
    health_score = round(100 - neg_ratio * 100, 1)

    with st.container(border=True):
        # ── header row ───────────────────────────────────────────
        header_left, header_right = st.columns([4, 1])
        with header_left:
            status_icon = "🟢" if is_active else "🔴"
            st.markdown(f"### {status_icon} {brand_name}")
        with header_right:
            lang_label = LANGUAGE_LABELS.get(language, language)
            country_label = COUNTRY_LABELS.get(country, country)
            st.caption(f"{lang_label} / {country_label}")

        # ── metrics row ──────────────────────────────────────────
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("Anahtar Kelime", len(keywords))
        with m2:
            st.metric("Toplam Öneri", stats.get("total_suggestions", 0))
        with m3:
            st.metric("Negatif", stats.get("negative_count", 0))
        with m4:
            if health_score >= 70:
                score_display = f"🟢 {health_score}"
            elif health_score >= 40:
                score_display = f"🟡 {health_score}"
            else:
                score_display = f"🔴 {health_score}"
            st.metric("Sağlık", score_display)
        with m5:
            st.metric("Son Tarama", format_date(stats.get("last_scan")))

        # ── keywords display ─────────────────────────────────────
        kw_display = ", ".join(f"`{kw}`" for kw in keywords[:8])
        if len(keywords) > 8:
            kw_display += f" +{len(keywords) - 8}"
        st.caption(f"Kelimeler: {kw_display}")

        # ── action buttons ───────────────────────────────────────
        btn_col1, btn_col2, btn_col3 = st.columns(3)

        with btn_col1:
            st.page_link(
                "pages/1_📊_Dashboard.py",
                label="📊 Dashboard",
                use_container_width=True,
            )

        # ── edit expander ────────────────────────────────────────
        with st.expander("✏️ Düzenle"):
            with st.form(f"edit_{brand_id}"):
                edit_name = st.text_input(
                    "Marka Adı", value=brand_name, key=f"edit_name_{brand_id}"
                )
                edit_keywords = st.text_area(
                    "Anahtar Kelimeler (satır satır)",
                    value=_keywords_to_text(brand.get("keywords", "[]")),
                    height=100,
                    key=f"edit_kw_{brand_id}",
                )

                ec1, ec2 = st.columns(2)
                with ec1:
                    lang_keys = list(LANGUAGE_OPTIONS.keys())
                    lang_idx = (
                        lang_keys.index(LANGUAGE_LABELS.get(language, "Türkçe"))
                        if LANGUAGE_LABELS.get(language) in lang_keys
                        else 0
                    )
                    edit_lang = st.selectbox(
                        "Dil",
                        lang_keys,
                        index=lang_idx,
                        key=f"edit_lang_{brand_id}",
                    )
                with ec2:
                    country_keys = list(COUNTRY_OPTIONS.keys())
                    country_idx = (
                        country_keys.index(COUNTRY_LABELS.get(country, "Türkiye"))
                        if COUNTRY_LABELS.get(country) in country_keys
                        else 0
                    )
                    edit_country = st.selectbox(
                        "Ülke",
                        country_keys,
                        index=country_idx,
                        key=f"edit_country_{brand_id}",
                    )

                eexp1, eexp2 = st.columns(2)
                with eexp1:
                    edit_az = st.checkbox(
                        "A-Z genişletme",
                        value=bool(brand.get("expand_az", True)),
                        key=f"edit_az_{brand_id}",
                    )
                with eexp2:
                    edit_tr = st.checkbox(
                        "Türkçe genişletme",
                        value=bool(brand.get("expand_turkish", True)),
                        key=f"edit_tr_{brand_id}",
                    )

                if st.form_submit_button("Güncelle", use_container_width=True):
                    updates = {}
                    new_kws = _parse_keywords(edit_keywords)

                    if edit_name.strip() and edit_name.strip() != brand_name:
                        updates["name"] = edit_name.strip()
                    if new_kws != keywords:
                        updates["keywords"] = new_kws
                    if LANGUAGE_OPTIONS[edit_lang] != language:
                        updates["language"] = LANGUAGE_OPTIONS[edit_lang]
                    if COUNTRY_OPTIONS[edit_country] != country:
                        updates["country"] = COUNTRY_OPTIONS[edit_country]
                    if edit_az != bool(brand.get("expand_az", True)):
                        updates["expand_az"] = edit_az
                    if edit_tr != bool(brand.get("expand_turkish", True)):
                        updates["expand_turkish"] = edit_tr

                    if updates:
                        try:
                            db.update_brand(brand_id, **updates)
                            st.success("Marka güncellendi!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Bu isimde bir marka zaten mevcut.")
                    else:
                        st.info("Değişiklik yapılmadı.")

        # ── deactivate / reactivate ──────────────────────────────
        if is_active:
            if st.button(
                "🗑️ Pasife Al",
                key=f"deactivate_{brand_id}",
                use_container_width=True,
            ):
                st.session_state[f"confirm_deactivate_{brand_id}"] = True

            if st.session_state.get(f"confirm_deactivate_{brand_id}"):
                st.warning(
                    f"**{brand_name}** pasife alınacak. Veriler silinmez, "
                    "marka taramalardan çıkarılır."
                )
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button(
                        "Evet, Pasife Al",
                        key=f"confirm_yes_{brand_id}",
                        type="primary",
                    ):
                        db.deactivate_brand(brand_id)
                        st.session_state.pop(f"confirm_deactivate_{brand_id}", None)
                        st.success(f"{brand_name} pasife alındı.")
                        st.rerun()
                with cc2:
                    if st.button(
                        "İptal",
                        key=f"confirm_no_{brand_id}",
                    ):
                        st.session_state.pop(f"confirm_deactivate_{brand_id}", None)
                        st.rerun()
        else:
            if st.button(
                "♻️ Aktif Et",
                key=f"reactivate_{brand_id}",
                use_container_width=True,
            ):
                db.update_brand(brand_id, active=True)
                st.success(f"{brand_name} tekrar aktif edildi!")
                st.rerun()
