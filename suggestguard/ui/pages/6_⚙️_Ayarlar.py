"""Ayarlar — application settings and notification configuration."""

from __future__ import annotations

import asyncio
from pathlib import Path

import streamlit as st

from suggestguard.config import SuggestGuardConfig, get_db
from suggestguard.ui.demo_data import seed_demo_data

# ── page setup ───────────────────────────────────────────────────────

st.header("⚙️ Ayarlar")
st.caption("Uygulama ayarları, bildirimler ve veritabanı yönetimi.")

db = get_db()
config = SuggestGuardConfig()
config.init_config()

# ======================================================================
# 1. Genel Ayarlar
# ======================================================================

st.subheader("Genel Ayarlar")

with st.form("general_settings"):
    gs1, gs2 = st.columns(2)

    with gs1:
        request_delay = st.number_input(
            "İstek Gecikmesi (saniye)",
            min_value=0.0,
            max_value=30.0,
            value=float(config.get("settings.request_delay", 1.5)),
            step=0.5,
            help="Google API istekleri arasındaki bekleme süresi.",
        )
        db_path = st.text_input(
            "Veritabanı Dosya Yolu",
            value=config.get("settings.database", "suggestguard.db"),
            help="SQLite veritabanı dosyasının yolu.",
        )

    with gs2:
        max_workers = st.number_input(
            "Paralel İstek Sayısı",
            min_value=1,
            max_value=10,
            value=int(config.get("settings.max_workers", 3)),
            step=1,
            help="Eşzamanlı çalışan istek sayısı.",
        )
        user_agent = st.text_input(
            "User Agent",
            value=config.get(
                "settings.user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            ),
            help="Google isteklerinde kullanılacak User-Agent başlığı.",
        )

    if st.form_submit_button("Kaydet", type="primary", use_container_width=True):
        config.data["settings"]["request_delay"] = request_delay
        config.data["settings"]["max_workers"] = int(max_workers)
        config.data["settings"]["database"] = db_path
        config.data["settings"]["user_agent"] = user_agent

        errors = config.validate()
        if errors:
            for err in errors:
                st.error(err)
        else:
            config.save()
            st.success("Ayarlar kaydedildi!")

# ======================================================================
# 2. Bildirim Ayarları
# ======================================================================

st.divider()
st.subheader("Bildirim Ayarları")

tab_tg, tab_slack, tab_webhook = st.tabs(["Telegram", "Slack", "Webhook"])

# ── Telegram ─────────────────────────────────────────────────────────

with tab_tg:
    tg_cfg = config.get("notifications.telegram", {})

    with st.form("telegram_settings"):
        tg_enabled = st.toggle(
            "Telegram Bildirimleri Aktif",
            value=bool(tg_cfg.get("enabled", False)),
        )
        tg_token = st.text_input(
            "Bot Token",
            value=tg_cfg.get("bot_token", ""),
            type="password",
            placeholder="123456:ABC-DEF...",
        )
        tg_chat_id = st.text_input(
            "Chat ID",
            value=str(tg_cfg.get("chat_id", "")),
            placeholder="-1001234567890",
        )

        tc1, tc2 = st.columns(2)
        with tc1:
            tg_save = st.form_submit_button("Kaydet", use_container_width=True)
        with tc2:
            tg_test = st.form_submit_button("Test Gönder", use_container_width=True)

    if tg_save:
        config.data.setdefault("notifications", {}).setdefault("telegram", {})
        config.data["notifications"]["telegram"]["enabled"] = tg_enabled
        config.data["notifications"]["telegram"]["bot_token"] = tg_token
        config.data["notifications"]["telegram"]["chat_id"] = tg_chat_id
        config.save()
        st.success("Telegram ayarları kaydedildi!")

    if tg_test:
        if not tg_token or not tg_chat_id:
            st.error("Bot Token ve Chat ID gerekli.")
        else:
            from suggestguard.notifiers.telegram import TelegramNotifier

            notifier = TelegramNotifier(tg_token, tg_chat_id)
            try:
                ok = asyncio.run(
                    notifier.send("🛡️ <b>SuggestGuard Test</b>\n\nTelegram bildirimi çalışıyor!")
                )
                if ok:
                    st.success("Test mesajı gönderildi!")
                else:
                    st.error("Mesaj gönderilemedi. Token ve Chat ID'yi kontrol edin.")
            except Exception as exc:
                st.error(f"Hata: {exc}")
            finally:
                asyncio.run(notifier.close())

# ── Slack ────────────────────────────────────────────────────────────

with tab_slack:
    slack_cfg = config.get("notifications.slack", {})

    with st.form("slack_settings"):
        slack_enabled = st.toggle(
            "Slack Bildirimleri Aktif",
            value=bool(slack_cfg.get("enabled", False)),
        )
        slack_url = st.text_input(
            "Webhook URL",
            value=slack_cfg.get("webhook_url", ""),
            type="password",
            placeholder="https://hooks.slack.com/services/...",
        )

        sc1, sc2 = st.columns(2)
        with sc1:
            slack_save = st.form_submit_button("Kaydet", use_container_width=True)
        with sc2:
            slack_test = st.form_submit_button("Test Gönder", use_container_width=True)

    if slack_save:
        config.data.setdefault("notifications", {}).setdefault("slack", {})
        config.data["notifications"]["slack"]["enabled"] = slack_enabled
        config.data["notifications"]["slack"]["webhook_url"] = slack_url
        config.save()
        st.success("Slack ayarları kaydedildi!")

    if slack_test:
        if not slack_url:
            st.error("Webhook URL gerekli.")
        else:
            from suggestguard.notifiers.slack import SlackNotifier

            notifier = SlackNotifier(slack_url)
            try:
                ok = asyncio.run(
                    notifier.send(":shield: *SuggestGuard Test*\n\nSlack bildirimi çalışıyor!")
                )
                if ok:
                    st.success("Test mesajı gönderildi!")
                else:
                    st.error("Mesaj gönderilemedi. Webhook URL'yi kontrol edin.")
            except Exception as exc:
                st.error(f"Hata: {exc}")
            finally:
                asyncio.run(notifier.close())

# ── Webhook ──────────────────────────────────────────────────────────

with tab_webhook:
    wh_cfg = config.get("notifications.webhook", {})
    if not isinstance(wh_cfg, dict):
        wh_cfg = {}

    with st.form("webhook_settings"):
        wh_enabled = st.toggle(
            "Webhook Bildirimleri Aktif",
            value=bool(wh_cfg.get("enabled", False)),
        )
        wh_url = st.text_input(
            "Webhook URL",
            value=wh_cfg.get("url", ""),
            placeholder="https://your-api.com/webhook",
        )
        wh_headers_raw = st.text_area(
            "Ek Başlıklar (satır satır: key: value)",
            value="\n".join(f"{k}: {v}" for k, v in wh_cfg.get("headers", {}).items()),
            height=80,
            placeholder="Authorization: Bearer xxx\nContent-Type: application/json",
        )

        wc1, wc2 = st.columns(2)
        with wc1:
            wh_save = st.form_submit_button("Kaydet", use_container_width=True)
        with wc2:
            wh_test = st.form_submit_button("Test Gönder", use_container_width=True)

    def _parse_headers(raw: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        for line in raw.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        return headers

    if wh_save:
        config.data.setdefault("notifications", {})["webhook"] = {
            "enabled": wh_enabled,
            "url": wh_url,
            "headers": _parse_headers(wh_headers_raw),
        }
        config.save()
        st.success("Webhook ayarları kaydedildi!")

    if wh_test:
        if not wh_url:
            st.error("Webhook URL gerekli.")
        else:
            from suggestguard.notifiers.webhook import WebhookNotifier

            notifier = WebhookNotifier(wh_url, _parse_headers(wh_headers_raw))
            try:
                ok = asyncio.run(
                    notifier.send(
                        {
                            "event": "test",
                            "source": "SuggestGuard",
                            "message": "Webhook bildirimi çalışıyor!",
                        }
                    )
                )
                if ok:
                    st.success("Test payload gönderildi!")
                else:
                    st.error("Gönderilemedi. URL ve başlıkları kontrol edin.")
            except Exception as exc:
                st.error(f"Hata: {exc}")
            finally:
                asyncio.run(notifier.close())

# ======================================================================
# 3. Veritabanı Yönetimi
# ======================================================================

st.divider()
st.subheader("Veritabanı")

# ── DB stats ─────────────────────────────────────────────────────────

db_file = Path(config.get("settings.database", "suggestguard.db"))

db_col1, db_col2, db_col3, db_col4 = st.columns(4)

with db_col1:
    if db_file.exists():
        size_mb = db_file.stat().st_size / (1024 * 1024)
        st.metric("DB Boyutu", f"{size_mb:.2f} MB")
    else:
        st.metric("DB Boyutu", "—")

with db_col2:
    brand_count = len(db.list_brands(active_only=False))
    st.metric("Marka Sayısı", brand_count)

with db_col3:
    row = db.conn.execute("SELECT COUNT(*) AS cnt FROM snapshots").fetchone()
    snapshot_count = row["cnt"] if row else 0
    st.metric("Tarama Sayısı", snapshot_count)

with db_col4:
    row = db.conn.execute("SELECT COUNT(*) AS cnt FROM suggestions").fetchone()
    suggestion_count = row["cnt"] if row else 0
    st.metric("Öneri Sayısı", suggestion_count)

# ── actions ──────────────────────────────────────────────────────────

act1, act2, act3 = st.columns(3)

# ── clean old data ───────────────────────────────────────────────────
with act1:
    with st.expander("🧹 Eski Veri Temizle"):
        clean_days = st.number_input(
            "Kaç günden eski?",
            min_value=7,
            max_value=365,
            value=90,
            step=7,
            key="clean_days",
        )
        if st.button("Temizle", key="clean_btn", use_container_width=True):
            st.session_state["confirm_clean"] = True

        if st.session_state.get("confirm_clean"):
            st.warning(
                f"{clean_days} günden eski taramalar ve öneriler silinecek. Bu işlem geri alınamaz!"
            )
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("Evet, Temizle", key="confirm_clean_yes", type="primary"):
                    from datetime import datetime, timedelta

                    cutoff = (datetime.now() - timedelta(days=clean_days)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    del_sugg = db.conn.execute(
                        "DELETE FROM suggestions WHERE last_seen < ?", (cutoff,)
                    )
                    del_snap = db.conn.execute(
                        "DELETE FROM snapshots WHERE taken_at < ?", (cutoff,)
                    )
                    db.conn.commit()
                    st.session_state.pop("confirm_clean", None)
                    st.success(f"{del_sugg.rowcount} öneri ve {del_snap.rowcount} tarama silindi.")
                    st.rerun()
            with cc2:
                if st.button("İptal", key="confirm_clean_no"):
                    st.session_state.pop("confirm_clean", None)
                    st.rerun()

# ── download DB ──────────────────────────────────────────────────────
with act2:
    if db_file.exists():
        st.download_button(
            "📥 Veritabanını İndir",
            data=db_file.read_bytes(),
            file_name=db_file.name,
            mime="application/x-sqlite3",
            use_container_width=True,
        )

# ── demo data ────────────────────────────────────────────────────────
with act3:
    if st.button("🎲 Demo Veri Yükle", use_container_width=True):
        with st.spinner("Demo veri oluşturuluyor..."):
            seed_demo_data(db)
        st.success("Demo veri oluşturuldu!")
        st.rerun()

# ── config file display ──────────────────────────────────────────────

with st.expander("📄 Yapılandırma Dosyası (suggestguard.yml)"):
    config_path = config.config_path
    if config_path.exists():
        st.code(config_path.read_text(encoding="utf-8"), language="yaml")
    else:
        st.info("Yapılandırma dosyası bulunamadı.")

# ======================================================================
# 4. Hakkında
# ======================================================================

st.divider()
st.subheader("Hakkında")

with st.container(border=True):
    about_left, about_right = st.columns([3, 1])

    with about_left:
        st.markdown(
            "**SuggestGuard** v0.1.0\n\n"
            "Google Autocomplete önerilerini izleyerek marka itibarını koruyan "
            "açık kaynak izleme aracı.\n\n"
            "- Otomatik tarama ve duygu analizi\n"
            "- Gerçek zamanlı bildirimler (Telegram, Slack, Webhook)\n"
            "- Kampanya takibi ve trend analizi\n"
            "- Detaylı raporlama ve dışa aktarım"
        )

    with about_right:
        st.image(
            "https://img.icons8.com/fluency/96/shield.png",
            width=64,
        )

    st.divider()

    link_col1, link_col2, link_col3 = st.columns(3)
    with link_col1:
        st.markdown("[GitHub](https://github.com/suggestguard/suggestguard)")
    with link_col2:
        st.markdown("[Dokümantasyon](https://github.com/suggestguard/suggestguard/wiki)")
    with link_col3:
        st.markdown("Lisans: **MIT**")
