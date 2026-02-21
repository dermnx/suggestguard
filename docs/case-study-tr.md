# Vaka Calismasi: E-Ticaret Markasinin Google Autocomplete Itibar Kurtarma Sureci

> Bu vaka calismasi, SuggestGuard kullanilarak gerceklestirilen bir itibar
> yonetimi kampanyasini detayli sekilde anlatmaktadir. Marka adi ve rakamlar
> gizlilik nedeniyle anonimlestirilmistir.

---

## Ozet

| Metrik | Oncesi | Sonrasi | Degisim |
|---|---|---|---|
| Negatif oneri orani | %40 | %15 | -%62.5 |
| Negatif oneri sayisi | 4/10 | 1.5/10 | -2.5 |
| Organik trafik | Baz | +%22 | Artis |
| Donusum orani | Baz | +%8 | Artis |
| Kampanya suresi | — | 30 gun | — |

---

## 1. Marka Profili

**Sektor:** E-Ticaret (Turkiye, B2C)
**Buyukluk:** Orta olcekli, aylik 50.000+ ziyaretci
**Urunler:** Elektronik aksesuar ve kisisel bakim urunleri
**Pazar:** Turkiye geneli, online satis agirlikli

Marka, 3 yildir faaliyet gostermekte ve sektorunde orta segmentte
yer almaktaydi. Marka bilinirliginin artmasiyla birlikte, Google aramalarinda
da gorunurlugu artmisti — ancak bu gorunurlugun bir kismi istenmeyen
iceriklerle doluydu.

---

## 2. Problem Tespiti

### Belirtiler

Markanin dijital pazarlama ekibi, 2024 yilinin son ceyreginde
asagidaki sorunlari fark etti:

- **Organik trafik dususu:** Google Analytics'te organik ziyaretlerde
  aciklanamayan %15'lik dusus
- **Donusum oraninda gerileme:** Siteye gelen ziyaretcilerin alis
  yapma orani %5 azaldi
- **Musteri geri bildirimleri:** "Google'da aratinca kotu seyler cikiyor"
  seklinde musteri yorumlari

### SuggestGuard ile Ilk Tarama

Marka adi SuggestGuard'a eklendi ve ilk tarama yapildi.
Sonuclar carpiciydi:

```
Toplam oneri: 10
Negatif:      4  (%40)
Pozitif:      2  (%20)
Notr:         4  (%40)

Negatif Kategoriler:
  fraud:     2  ("marka dolandirici", "marka sahte")
  complaint: 1  ("marka sikayet")
  refund:    1  ("marka iade")
```

**Skor:** 60/100 (Dusuk)

Her bes Google aramasinin ikisinde potansiyel musteri, marka hakkinda
negatif bir oneri goruyordu. "Marka dolandirici" onerisi listenin
3. sirasindaydi — yani her aramada gorunur durumdaydi.

### Kok Neden Analizi

SuggestGuard'in trend analizi ile negatif onerilerin kaynaklari
arastirildi:

1. **"marka dolandirici" ve "marka sahte"** — 2 ay once baslamis,
   bir forum sitesindeki asilsiz bir paylasimindan kaynaklaniyor.
   Kullanicilar bu terimi aratmis ve Google oneri olarak sunmaya
   baslamis.

2. **"marka sikayet"** — Gercek musteri sikayetlerinden kaynaklaniyor.
   Sikayetvar.com'da 3 cozumlenmemis sikayet mevcut.

3. **"marka iade"** — Iade politikasinin net olmamasi nedeniyle
   sikca aratilan bir terim. Aslinda notr bir arama ama negatif
   algilaniyordu.

---

## 3. Strateji

SuggestGuard'in kampanya modulu kullanilarak 30 gunluk bir
iyilestirme plani olusturuldu.

### Hedefler

- Negatif oneri oranini %40'tan %20'nin altina dusurmek
- "dolandirici" ve "sahte" onerilerini tamamen yok etmek
- Pozitif onerilerin oranini artirmak

### Aksiyon Plani

| Hafta | Aksiyon | Sorumlu |
|---|---|---|
| 1 | SuggestGuard kampanyasi baslat, gunluk tarama aktif et | Dijital Pazarlama |
| 1 | Telegram bildirimlerini aktif et | DevOps |
| 1-2 | Sikayetvar sikayetlerini cozumle | Musteri Hizmetleri |
| 1-2 | Iade politikasi sayfasini yenile ve SEO optimize et | Icerik Ekibi |
| 2-3 | Pozitif icerik stratejisi: 10 blog yazisi, 5 musteri referansi | Icerik + PR |
| 2-3 | Google My Business profilini guncelle, degerlendirme kampanyasi | Pazarlama |
| 3-4 | Yetkili kaynaklarda basin bultenleri yayinla | PR |
| 4 | Kampanya raporu cikar, sonuclari degerlendir | Tum Ekip |

---

## 4. Uygulama Sureci

### Hafta 1: Izleme Altyapisi

SuggestGuard'da kampanya baslatildi: **"Itibar Iyilestirme Kampanyasi"**

Yapilandirma:
- Gunluk otomatik tarama (cron, sabah 09:00)
- Telegram bildirimleri aktif (yeni negatif oneri geldiginde aninda uyari)
- Dashboard'a tum ekip erisimi saglandi

Ilk hafta SuggestGuard dashboard'u gunluk izlendi. Negatif oran sabit
kaldi (%38-42 arasinda dalgalandi).

### Hafta 2: Icerik Mudahalesi

**Sikayet Yonetimi:**
- Sikayetvar'daki 3 sikayet iletisime gecilerek cozumlendi
- Her birine kamuya acik yanit yazildi
- Cozum sureci SuggestGuard notlarina eklendi

**Iade Politikasi:**
- Iade sayfasi yeniden yazildi, SSS eklendi
- "Marka iade kosullari" icin optimize edilmis icerik yayinlandi
- Bu sayfanin Google'da ust siralara cikmasi hedeflendi

SuggestGuard dashboard'unda ikinci haftanin sonunda "marka iade" onerisi
notr olarak yeniden siniflandirildi (icerik iyilestirmesi sonrasi).

### Hafta 3: Pozitif Sinyal Uretimi

**Blog Icerikleri:**
- "Marka musteri yorumlari 2024" (gercek pozitif referanslar)
- "Marka guvenilir mi? Tum detaylar" (SEO hedefli)
- "Marka en iyi urunler" (urun odakli pozitif icerik)
- Toplam 8 blog yazisi yayinlandi

**PR Calismalari:**
- 2 basin bulteni yetkili haber sitelerinde yayinlandi
- Google My Business'ta 50+ yeni degerlendirme toplandi (4.5+ yildiz)

SuggestGuard trend analizi:
```
Yukselen negatif:  0  (yeni negatif yok!)
Dusen negatif:     1  ("marka dolandirici" pozisyon 3 → 7)
Kalici negatif:    2  ("marka sahte", "marka sikayet")
Negatif oran:      %30 (onceki hafta %38)
```

### Hafta 4: Sonuc ve Raporlama

Kampanya son haftasinda SuggestGuard metrikleri:

```
Toplam oneri: 10
Negatif:      1.5  (%15)
Pozitif:      4    (%40)
Notr:         4.5  (%45)

Kaybolan negatifler:
  ✅ "marka dolandirici"  (tamamen kayboldu)
  ✅ "marka sahte"        (tamamen kayboldu)

Kalan negatifler:
  ⚠️ "marka sikayet"     (pozisyon 8, azalan gorunurluk)

Yeni pozitifler:
  🟢 "marka en iyi urunler"
  🟢 "marka guvenilir"
```

SuggestGuard'in **Kampanya Raporu** fonksiyonu ile detayli
once/sonra karsilastirma belgesi olusturuldu.

---

## 5. Sonuclar

### Kantitatif Sonuclar

| Metrik | Kampanya Oncesi | Kampanya Sonrasi | Degisim |
|---|---|---|---|
| Negatif oneri sayisi | 4 | ~1.5 | -%62.5 |
| Negatif oneri orani | %40 | %15 | -25 puan |
| Pozitif oneri sayisi | 2 | 4 | +%100 |
| Saglik skoru | 60 | 85 | +25 puan |
| Organik trafik | Baz | +%22 | Artis |
| Donusum orani | Baz | +%8 | Artis |

### Kalitatif Sonuclar

- Musteri hizmetlerine "Google'da kotu seyler cikiyor" sikayeti **sifira** indi
- Satis ekibi, potansiyel musterilerin guven sorusu sormadan alisveris
  yaptigini raporladi
- Marka algisi anketinde "guvenilir" orani %34'ten %67'ye yukseldi

### SuggestGuard'in Katkilari

1. **Erken tespit:** Negatif onerilerin varligini, kategorisini ve siddetini
   ilk taramada ortaya koydu
2. **Gunluk izleme:** Cron + Telegram entegrasyonu ile her gun otomatik
   tarama ve uyari sagladi
3. **Trend analizi:** Hangi negatifin dususte, hangisinin kalici oldugunu
   gostererek mudahale onceliklerini belirledi
4. **Kampanya olcumu:** Once/sonra karsilastirma ile yapilan calismanin
   somut etkisini kanitladi
5. **Raporlama:** HTML rapor disa aktarimi ile yonetime sunulabilir
   belge uretildi

---

## 6. Ders Cikarimlar

### Ne Ise Yaradi

- **Hiz:** SuggestGuard ile ilk tarama 2 dakikada tamamlandi.
  Manuel kontrol ile bu is gunler alirdi.
- **Kategorizasyon:** Negatif onerilerin "fraud" ve "complaint" olarak
  siniflandirilmasi, farkli mudahale stratejileri gelistirmeyi sagladi.
- **Gunluk veri:** Trend grafikleri sayesinde, hangi aksiyonun ne kadar
  etkili oldugu bireysel olarak olculebildi.
- **Kampanya modu:** Baslangic/bitis tarihleri ile otomatik once/sonra
  karsilastirma, ekstra efor gerektirmeden sonuc belgesi uretti.

### Zorluklar

- Google autocomplete onerileri **yavaş degisir**. Ilk 2 haftada
  belirgin bir iyilesme gormek zordur — sabir gerektirir.
- Bazi negatif oneriler (ozellikle "sikayet") tamamen yok edilemeyebilir.
  Ancak pozisyonlari asagiya cekilerek gorunurlugu azaltilabilir.
- Cok sayida marka kelimesi olan sirketlerde tarama suresi uzayabilir.
  `max_workers` ayari ile optimize edilmeli.

### Onerimiz

1. **Reaktif degil, proaktif olun.** SuggestGuard'i marka adini
   tescil ettiginiz gun kurun. Negatif oneriler olusmadan once
   pozitif sinyaller uretin.
2. **Gunluk taramayi ihmal etmeyin.** Yeni bir negatif oneri
   oluştugunda 24 saat icinde mudahale etmek, 30 gun sonra
   mudahale etmekten 10 kat daha etkilidir.
3. **Kampanya modunu kullanin.** Her iyilestirme calismasini
   SuggestGuard kampanyasi olarak kaydedin. 3 ay sonra yonetime
   "ne yaptik, ne kazandik" diye soruldiginda elinizde veri olsun.

---

## 7. Teknik Detaylar

### Kullanilan SuggestGuard Ozellikleri

| Ozellik | Kullanim |
|---|---|
| Otomatik tarama (CLI + cron) | Gunluk 09:00 zamanlanmis tarama |
| Turke duygu analizi | 6 kategori: fraud, complaint, legal, quality, refund, trust |
| Trend analizi | Yukselen / dusen / kalici negatif tespiti |
| Kampanya yonetimi | 30 gunluk kampanya, once/sonra karsilastirma |
| Telegram bildirimleri | Yeni negatif onerilerde anlik uyari |
| HTML rapor disa aktarim | Yonetime sunulabilir kampanya raporu |
| Plotly grafikleri | Negatif oran trendi, duygu dagilimi pie chart |

### Tarama Yapılandirmasi

```yaml
settings:
  request_delay: 2.0    # Google rate-limit'e dikkat
  max_workers: 2         # Konservatif paralellik
  database: suggestguard.db

notifications:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
```

### Tarama Istatistikleri

- Marka kelimesi: 2 ("marka", "marka com")
- A-Z genisletme: Aktif (26 harf + 7 Turkce karakter = 33 varyant/kelime)
- Toplam sorgu/tarama: ~70
- Tarama suresi: ~2 dakika
- 30 gunluk toplam tarama: 30
- Toplam sorgu: ~2.100

---

*Bu vaka calismasi SuggestGuard v0.1.0 ile gerceklestirilmistir.
Guncel ozellikler icin [README.md](../README.md) dosyasina bakiniz.*
