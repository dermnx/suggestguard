# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-06-01

### Added

- **Tarama Motoru:** Google Autocomplete API ile otomatik tamamlama önerisi toplama
- **A-Z Genişletme:** Her harf ve Türkçe karakterler (ç, ğ, ı, ö, ş, ü) ile varyant üretimi
- **Duygu Analizi:** Türkçe + İngilizce keyword-based sentiment sınıflandırması
- **6 Negatif Kategori:** fraud, complaint, legal, quality, refund, trust
- **Trend Analizi:** Yükselen, düşen ve kalıcı negatif tespiti
- **SQLite Veritabanı:** WAL mode, foreign keys, otomatik şema oluşturma
- **Streamlit Dashboard:** 6 sayfa (Dashboard, Tarama, Raporlar, Markalar, Kampanyalar, Ayarlar)
- **Plotly Grafikler:** Interaktif pie, line, bar, stacked bar chart — dark theme
- **Kampanya Yönetimi:** Kampanya başlat/bitir, önce/sonra karşılaştırma
- **Bildirimler:** Telegram, Slack, Webhook — yeni negatif önerilerde anlık alarm
- **Dışa Aktarım:** CSV, JSON, HTML rapor formatları
- **CLI Tarama:** `suggestguard-scan` komutu, cron desteği
- **Demo Veri:** Ayarlar sayfasından tek tıkla örnek veri yükleme
- **Marka Yönetimi:** Çoklu marka, keyword yönetimi, aktif/pasif kontrolü
- **284 Test:** pytest + pytest-asyncio, tüm modüller için birim ve entegrasyon testleri
- **CI Pipeline:** GitHub Actions — Python 3.10/3.11/3.12, ruff check, ruff format, pytest
- **Dokümantasyon:** README.md, Türkçe vaka çalışması (docs/case-study-tr.md)

[0.1.0]: https://github.com/dermnx/suggestguard/releases/tag/v0.1.0
