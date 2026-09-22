# AutoSense B2C — Proje Brief'i

> Bu dosya, projeyi hiç bilmeyen bir değerlendiriciye (insan ya da model)
> tek seferde bağlam vermek için yazıldı. `GPT-DEGERLENDIRME-PROMPTU.md`
> ile birlikte kullanılır: önce bu metin, sonra o prompt yapıştırılır.
> Rakamlar 13 Eylül 2026 tarihli depo durumundan alındı.

---

## 1. Tek cümlede

AutoSense B2C, Türkiye'deki ikinci el araç alıcısının önündeki tek bir ilanı
alıp — "bu fiyat gerçekten uygun mu?" sorusuna — piyasa verisiyle ölçülmüş,
tekrarlanabilir ve gerekçeli bir cevap veren web uygulamasıdır.

## 2. Kullanıcı ve problem

**Kullanıcı:** arabam.com / sahibinden.com'da bir ilana bakan, araba almak
üzere olan bireysel alıcı. Uzman değil; ekspertiz raporu okumayı bilmiyor;
"bu araç kaç para eder" sorusunun cevabını forumlardan ve tanıdıklardan
arıyor.

**Problem:**

- İlan fiyatı ile gerçek piyasa değeri arasındaki farkı ölçemiyor.
- İlan metni pazarlama dili: "hatasız, boyasız, tramersiz" gibi ifadelerin
  hangisinin araç bilgisiyle çeliştiğini göremiyor.
- Pazarlığa hangi rakamdan başlayacağını, nereye kadar ineceğini bilmiyor.
- Aracın 1–3 yıl sonraki değerini ve yıllık taşıma maliyetini hesaba katmıyor.
- Bölgesel fiyat farkını (aynı araç Van'da ucuz, İstanbul'da pahalı) bilmiyor.

**Ürünün vaadi:** kullanıcı aracın bilgilerini girer (ya da ilan metnini
yapıştırır), 11 kartlık bir analiz raporu alır. Rapor "al / alma" demez;
kararı verecek sayıyı ve gerekçesini önüne koyar.

## 3. Uçtan uca kullanıcı akışı

1. **Kayıt** — e-posta + parola. Zorunlu e-posta doğrulaması (6 haneli kod).
2. **Giriş** — session cookie. Doğrulanmamış hesap analiz ekranını göremez.
3. **Form** — iki kolon:
   - Sol: kategori, marka, seri, motor, paket, model yılı, km, ilan fiyatı,
     il/ilçe, renk, yakıt, vites, ilan açıklaması. Marka→seri→motor→paket
     kademeli olarak birbirine bağlı.
   - Sağ: **hasar şeması** — 13 parçalı araç şeması (ön/arka tampon,
     çamurluklar, kapılar, kaput, tavan, bagaj). Her parçaya tıklayınca
     durum döner: Orijinal → Lokal boyalı → Boyalı → Değişen.
4. **Kısayol** — "İlan metninden otomatik doldur": kullanıcı arabam.com veya
   sahibinden.com ilan sayfasının tüm metnini yapıştırır; sistem metni parse
   edip marka/seri/motor/paket/yıl/km/fiyat/il/renk/vites/hasar haritasını
   forma doldurur.
5. **Analiz** — tek POST, tek yanıt. Ekranda 11 kart.
6. **Paylaş / PDF** — `window.print()` ile yazdırma ve Web Share API.

## 4. Analiz çıktısı — 11 kart

| # | Kart | Ne gösterir | Veri kaynağı |
|---|---|---|---|
| 0 | **Karar kartı** | 10 üzerinden skor, "pahalı/uygun/fırsat" etiketi, ilan fiyatı vs tahmini değer, tahmin aralığı, güven % | tahmin motoru |
| 1 | **Pazarlık planı** | Açılış teklifi / hedef fiyat / tavan fiyat + hedefe inilirse kazanç | tahmin + emsal medyanı |
| 2 | **Fiyatı etkileyen kalemler** | Km, hasar, vites, renk, bölge — her birinin tahmine yüzde etkisi (± tornado) | motorun kendi katsayıları |
| 3 | **Değer kaybı projeksiyonu** | Bugün / 1 yıl / 3 yıl sonraki tahmini değer ve kayıp | yaş grubu değer kaybı serisi |
| 4 | **İlan kalitesi ve belirsizlik** | 100 üzerinden veri riski skoru + "100 puandan ne götürdü" kırılımı | sabit eşikli kural seti |
| 5 | **Açıklama analizi** | İlan metninden çıkarılan iddialar, çelişkiler, olumlu sinyaller, değinilmemiş konular + metnin fiyata etkisi | regex kural motoru |
| 6 | **Satıcıya mutlaka sorun** | Çelişkiler ve eksiklerden türetilen somut soru listesi | 4 + 5'in birleşimi |
| 7 | **Bölgesel fiyat sinyali** | Seçilen ilin ülke ortalamasına yüzde farkı + sinyal güveni | galeri ilanları |
| 8 | **Piyasa fiyat trendi** | Son 90 günde aynı model/yılın ortalama ilan fiyatı hareketi | galeri snapshot serisi |
| 9 | **Yayındaki benzer ilanlar** | Aynı model ±1 yıl, canlı emsaller; fiyat farkı ve ilan yaşı | galeri ilanları |
| 10 | **Yıllık sahip olma maliyeti** | Yakıt + MTV + sigorta + bakım, 15.000 km/yıl varsayımıyla | TCO modülü |

## 5. Tahmin motoru — metodoloji

**Kritik tasarım kararı: makine öğrenmesi ya da LLM YOK.** Tahmin tamamen
paket referans fiyatlarına (baseline) dayanır.

- **Referans (baseline):** `paket_fiyatlari.db` — marka/seri/motor/paket
  kırılımında referans fiyat. Aynı yaprağın en düşük km'li ilk 5 ilanının
  referansı alınır.
- **Uygulanan çarpanlar:** `km_factor` (referans km'ye göre),
  `damage_factor` (boyalı/değişen parçaların toplam etkisi), `gear_factor`
  (vites), renk primi (emsal galeri ilanlarından hesaplanır), ağır hasar.
- **Paket bilinmiyorsa:** o motorun altındaki tüm paketlerin tahmini
  hesaplanıp medyanı alınır; kullanıcıya hangi paketlerin hesaba katıldığı
  söylenir (`package_fallback`).
- **Güven yüzdesi** ve **tahmin aralığı** (low–high) döner.
- Referans DB'nin `mtime`'ı her çağrıda kontrol edilir; scraper DB'yi
  güncellerse uzun ömürlü worker cache'i kendi kendine tazelenir.

**Neden ML değil:** aynı girdi her zaman aynı çıktıyı vermeli. Kullanıcıya
"neden bu fiyat" diye sorulduğunda gösterilecek bir kural zinciri olmalı.
Bu, ürünün temel farklılaştırıcısı olarak konumlandırılmış durumda.

## 6. Açıklama analizi — metin motoru

Dosyada büyük harflerle yazılı: **LLM KULLANILMIYOR.** Her iddia,
adlandırılmış bir regex kalıbının eşleşmesidir.

- **23 iddia kalıbı:** hasarsız, boyasız, değişensiz, hatasız, ağır hasar/pert,
  bakımlı, tek el, garanti, masrafsız, takas, kredi, metinde değişenden söz
  ediliyor, metinde boyadan söz ediliyor, ekspertiz, acil satış vurgusu,
  pazarlık yok, ticari/filo, faturalı, yetki belgesi, muayene, kasko,
  yedek anahtar, olumsuzu "sadece/yalnızca" ile küçümseme.
- **Çelişki tespiti:** metindeki iddia ile kullanıcının forma girdiği veri
  karşılaştırılır. "Değişensiz" yazıyor ama formda 3 parça değişmiş işaretli
  → çelişki. Ürünün en güçlü pazarlık kozu olarak konumlandırılmış.
- **Galeri politika cümlesi filtresi:** "ağır hasarlı araç almıyoruz" gibi
  galerinin genel politikasını anlatan cümleler, aracın kendi durumu sanılmasın
  diye cümle bazında eleniyor. 791 ilanlık örneklemde potansiyel çelişki
  adaylarının %76'sı bu şekilde yanlış pozitifmiş.
- **Ek çıkarımlar:** tramer tutarı, ekspertiz raporu blokları, metindeki km
  iddiaları, yapısal/güvenlik-kritik parça bulguları, "gürültü oranı"
  (reklam/dolgu metin oranı).
- **Fiyat etkisi (`price_impact`):** metinden çıkan sinyaller tek bir yüzdeye
  indirgenir; negatif tarafta −%20, pozitif tarafta +%6 tavanı var. İlan
  fiyatı → metne göre düzeltilmiş fiyat olarak gösterilir.

Kod içindeki yorumlar, geçmişte yapılmış hataları ve neden öyle yazıldığını
anlatıyor (ör. `\bpert\b` sınırı olmadan yazıldığında "ekspertiz" kelimesindeki
alt-dizi yüzünden 791 ilanın %43'ü yanlışlıkla ağır hasarlı işaretlenmiş;
gerçek oran %6).

## 7. İlan kalitesi skoru — sabit rubrik

100 puandan başlar, her kural sabit puan düşer. Yoruma yer yok:

| Kural | Puan |
|---|---|
| Ağır hasar kaydı | −35 |
| 3+ parça değişmiş | −25 (1–2 parça: −10) |
| 5+ parça boyalı | −15 |
| Fiyat piyasanın %20+ altında | −15 |
| Her çelişki | −12 |
| Yıllık ortalama 35.000 km üzeri | −10 |
| 300.000 km üzeri | −10 |
| Açıklama çok zayıf (skor ≤3) | −8 |
| Her değinilmemiş konu | −3 |
| Açıklama girilmemiş | −5 |
| Renk / vites / il belirtilmemiş | her biri −3 |

Skor ≥80 "düşük risk", ≥55 "orta risk", altı "yüksek risk".

## 8. Veri katmanı

Üç ayrı SQLite dosyası, hepsi **salt okunur snapshot** (otomatik güncelleme yok):

| Dosya | İçerik | Büyüklük |
|---|---|---|
| `galeri.db` | Galeri ilanı snapshot'ları | **1.355.650 ilan**, 2.242 galeri, 2026-06-15 → 2026-09-05 (~975 MB) |
| `paket_fiyatlari.db` | Paket referans fiyatları | 8.201 yaprak (marka-seri-motor-paket), 16.402 varyant, 6.384 eksik referans kaydı |
| `listings.sqlite3` | Analiz edilmiş ilan arşivi | 1.039 ilan (tahmin, hasar skoru, açıklama dahil) |
| `accounts.sqlite3` | B2C hesapları | yerelde; yayında ayrı PostgreSQL |

Yenileme: `scripts/import_reference_data.py` ile kaynak projeden manuel
aktarım. Bütünlük kontrolünden geçmeyen dosya yerleştirilmiyor.

## 9. Teknik mimari

**Backend:** Django 5.2 + DRF + django-allauth (headless). Ayrı B2C servisi;
B2B uygulamasından bağımsız ayarlar, veritabanı, cookie adı ve secret.

- Kimlik: session cookie (HttpOnly, Secure, SameSite=Lax, host kapsamlı ad).
  Token localStorage'a yazılmıyor. Yazma isteklerinde CSRF.
- Korunan uçlar: `/api/b2c/vehicles`, `/locations`, `/vehicle-defaults`,
  `/analyze`, `/lookup-text`. Hepsi `VerifiedUser` (aktif + e-postası
  doğrulanmış) + özellik yetkisi permission'ı ardında.
- Hız sınırı: analiz 20/dk, ilan metni 30/dk, okuma 120/dk. Yayında paylaşımlı
  Redis zorunlu (yoksa servis başlamıyor).
- Referans veritabanlarına yazma ve migration engelli.

**Frontend:** React 19 + TypeScript 5.9 + Vite 8. React Router 7. Kendi tasarım
sistemi (`tone-*` kart renk kimliği), harici UI kütüphanesi yok. Tüm grafikler
elde yazılmış (SVG + CSS), grafik kütüphanesi bağımlılığı yok.

**Yayın:** Docker Compose + Caddy (TLS sonlandırma, statik servis, `/api/*` ve
`/_allauth/*` yönlendirmesi) + PostgreSQL + Redis. Backend/DB/Redis host portu
açmıyor. Production ayarları eksik secret, HTTPS, Redis veya SMTP
yapılandırmasında başlamıyor.

**Test:** 74 backend testi, 3 yerel tarayıcı (Playwright) testi, 1 HTTPS/SMTP
tarayıcı testi. Yerel yayın-benzeri ortam Mailpit ile gerçek SMTP akışını
test ediyor.

## 10. Şu anda OLMAYANLAR

Değerlendirme yapılırken en kritik bölüm bu.

**Ürün tarafı:**

- Ödeme, abonelik, premium plan — hiç yok. Tüm özellikler doğrulanmış her
  kullanıcıya açık. Özellik yetkisi altyapısı (`/api/b2c/me` + `has_feature`)
  hazır ama tek plan var.
- **Analiz geçmişi yok.** Kullanıcı yaptığı analizi kaydedemiyor, sonra
  açamıyor, iki aracı yan yana karşılaştıramıyor.
- **Takip / uyarı yok.** "Bu ilanın fiyatı düşerse haber ver" yok.
- **Favori / liste yok.**
- Mobil uygulama yok (web mobil uyumlu).
- Fotoğraf analizi yok — kullanıcı fotoğraf yükleyemiyor.
- VIN / şasi numarası sorgusu yok. Gerçek tramer sorgusu yok (yalnızca ilan
  metninde geçen tramer tutarı okunuyor).
- Ekspertiz firması, sigorta, kredi gibi hiçbir üçüncü taraf entegrasyonu yok.
- Satıcıya gönderilecek hazır mesaj/pazarlık metni üretimi yok.
- Kullanıcı geri bildirimi toplanmıyor ("bu tahmin doğru muydu?").
- Onboarding, örnek analiz, boş durum eğitimi yok — kullanıcı ilk girdiğinde
  boş formla karşılaşıyor.
- Türkçe dışında dil yok.

**Veri tarafı:**

- Snapshot'lar manuel yenileniyor; canlı besleme yok.
- `paket_fiyatlari.db`'de 6.384 eksik referans kaydı var — bazı araçlar için
  paket bazlı referans yok.
- Analiz edilmiş ilan arşivi yalnızca 1.039 kayıt.
- Gerçekleşen satış fiyatı verisi yok — her şey **ilan** fiyatı üzerinden.
  Yani "istenen fiyat" biliniyor, "satılan fiyat" bilinmiyor.
- Tahminin doğruluğu ölçülmüyor; geriye dönük backtest yok.

**Teknik tarafı:**

- Canlı domain ve doğrulanmış SMTP göndericisi henüz kurulmadı; yayına
  çıkılmadı.
- Eski Autosense sunucusundaki açık `/api/b2c/*` yolları hâlâ açık; geçişte
  kapatılacak.
- Gözlemlenebilirlik (log toplama, hata izleme, metrik) kurulmadı.
- CI yok; testler elle çalıştırılıyor.

## 11. Değişmez ilkeler

Bir öneri bu ilkelerden birini kırıyorsa, kırdığını açıkça söylemeli:

1. **Determinizm.** Aynı girdi her zaman aynı çıktıyı verir. Tahminde ve
   skorlamada ML/LLM kullanılmıyor.
2. **Skorlar sabit rubriklerle hesaplanır.** "Model bunu 7 verdi" yok;
   "şu kural −12 puan götürdü" var. LLM-as-a-judge kesinlikle kullanılmaz.
3. **Gerekçe gösterilir.** Her sayının arkasında kullanıcıya gösterilebilir
   bir kural veya emsal seti var.
4. **Ürün karar vermez.** "Alma" demez; alıcının kendi kararını verebilmesi
   için sayıyı ve gerekçeyi verir.
5. **Yasal sınır.** Çıktı istatistiksel tahmindir; ekspertiz raporu, tramer
   sorgusu veya resmî değerleme yerine geçmez — her raporda yazılı.
