# AutoSense — kronik/artı-eksi veri üretimi (Codex CLI devir brief'i)

> Bu metni Codex CLI'a ver (`codex exec` veya interaktif oturum).
> Ön koşul: bu repo kökünde çalıştır — `research/kronik-pilot/` içinden yol veriyorum.
> Bu, Claude oturumlarının kullandığı `DEVAM-PROMPTU.md` ile AYNI işi, aynı kurallarla
> sürdürüyor. Tek fark: sonunda bir KENDİ KENDİNE DOĞRULAMA adımı ekli (aşağıda).

---

## Bağlam

AutoSense B2C: Türkiye'de ikinci el araç ilanı için fiyat/pazarlık analizi veren
web uygulaması (Django + Vite). Analiz raporuna 12. kart olarak
**"bu motorun kronik arızaları + iyi/kötü yönleri"** ekleniyor.

Veri şu an üretiliyor: 300 hedef motorun bir kısmı tamam. Güncel sayıyı ilk adımda
kendin doğrula (aşağıya bak).

## Değişmez kurallar

1. **Runtime'da LLM yok.** Bu üretim offline ve tek seferlik; ürün çalışırken
   sadece hazır veriye lookup yapacak. Tekrarlanabilir çıktı ürünün temel
   farklılaştırıcısı — bunu bozma.
2. **Kapalı kitap yasak.** Hiçbir iddia hafızandan yazılmaz. Her iddia gerçekten
   açılmış/aranmış bir kaynağa dayanır.
3. **Uydurma URL yasak.** Açılamayan, 404 veren, aramada görülmeyen adres yazılmaz.
   Kaynak bulunamayan iddia hiç yazılmaz. Boş liste kabul edilebilir sonuçtur.
4. **Kapalı etiket seti.** `etiketler.json` dışında etiket üretilmez.
5. **Değerlendirmeyi LLM'e yaptırma.** Bu görevde sadece üretim var; kalite ölçümü
   ayrı ve elle yapılıyor — sen değerlendirme/skorlama yapma.
6. **YENİ — kendi kendine kaynak doğrulama (zorunlu, atlanamaz):**
   Bir kaydı JSON'a yazmadan ÖNCE, `kaynak_url`'i **ikinci kez** aç/fetch et ve
   `kaynak_alinti` metninin o sayfada GERÇEKTEN geçtiğini kontrol et (küçük
   boşluk/noktalama farkları tolere edilebilir, ama cümle sayfada bulunmalı).
   - Sayfa artık açılmıyorsa, alıntı sayfada yoksa, ya da emin değilsen: **kaydı ekleme.**
   - İlk aramada "bulduğuna" güvenip geçme — bu ayrı, bilinçli bir ikinci kontrol adımı.
   - Bu adımı her kayıt için tek tek yap, atlarsan görev eksik sayılır.

## Çalışma klasörü

Repo kökünden: `research/kronik-pilot/`

```
targets_production.json     300 hedef (marka+seri+motor, ilan sayısına göre sıralı) — DEĞİŞTİRME
prompt_B_kaynakli.md        prompt şablonu — DEĞİŞTİRME
etiketler.json              kapalı etiket setleri — DEĞİŞTİRME
dogrulama.py                şema doğrulama, tek doğruluk kaynağı
render_prompts.py           sıradaki hedefler için prompt üretir
ingest_uretim.py            ham çıktıları doğrular, temiz JSON yazar
rendered_uretim/<id>.md     hazır promptlar (render_prompts.py üretir)
ham_uretim/B/<id>.json      SENİN yazacağın ham çıktı — bu dosyayı sen üretiyorsun
ciktilar_uretim/B/          ingest_uretim.py'nin doğrulanmış çıktısı
DURUM.md                    durum notu — iş bitince/duraklatınca güncelle
```

Pilot klasörlerine (`ciktilar/`, `ham/`, `degerlendirme.csv`) **dokunma** — ayrı bir
ölçümün verisi.

## Model ve araç önerisi

Ucuz + web search destekli bir model kullan (örn. Codex CLI'da mevcutsa
`gpt-5.6-luna` ya da `gpt-5.4-mini`). Canlı web araması gerekiyor çünkü kaynaklar
güncel forum/şikayet sayfaları — cached/offline arama modu yetersiz kalabilir,
`--search` (live) bayrağını veya eşdeğerini kullan.

Model seçimi ve paralellik tamamen sana kalmış — istersen birden fazla hedefi
ayrı süreçlerde paralel işleyebilirsin (Claude tarafında 13'erli paralel subagent
yapılıyordu), istersen sıralı ilerleyebilirsin. Önemli olan aşağıdaki akış ve
kurallara uyulması.

## Akış

1. **Durumu doğrula:**
   ```bash
   cd research/kronik-pilot && python3 render_prompts.py 13 --liste
   ```
2. **Parti hazırla:**
   ```bash
   python3 render_prompts.py 13
   ```
   Tamamlanmış hedefleri atlar, sıradaki hedefler için `rendered_uretim/<id>.md` üretir.
3. **Her hedef için:** `rendered_uretim/<id>.md` dosyasını oku, içindeki talimatı
   aynen uygula (web'de ara, iddiaları topla, şemaya uy).
4. **Kendi kendine doğrulama (Değişmez kural 6):** JSON'a yazmadan önce her kaydın
   kaynağını tekrar aç ve alıntıyı doğrula. Geçmeyen kayıtları çıkar.
5. **Yaz:** Doğrulanmış JSON'u `ham_uretim/B/<id>.json`'a yaz. Dosya biçimi:
   ```json
   {
     "hedef_id": "<hedef id>",
     "kayitlar": [
       {
         "tip": "kronik",
         "etiket": "turbo",
         "iddia": "Tek cümle, en fazla 140 karakter, somut.",
         "km_araligi": "120.000+ km",
         "kaynak_url": "https://...",
         "kaynak_alinti": "Sayfadan birebir kopyalanmış cümle.",
         "guven": "yuksek"
       }
     ]
   }
   ```
   - `tip`: `kronik` | `iyi` | `kotu`
   - `etiket`: `etiketler.json`'daki ilgili listeden, dışına çıkılamaz
   - `km_araligi`: sadece kronikte ve biliniyorsa, yoksa `null`
   - `guven`: `yuksek` (3+ bağımsız kaynak) | `orta` (2) | `dusuk` (1)
   - Üst sınır: 8 kronik, 5 iyi, 5 kötü
6. **Parti bitince doğrula:**
   ```bash
   python3 ingest_uretim.py
   ```
   Şema ihlali sıfırdan büyükse **dur ve kullanıcıya bildir** (şu ana kadar
   700+ kayıtta sıfırdı; ihlal çıkması bir şeyin bozulduğu anlamına gelir).
7. **Siteye yansıt:**
   ```bash
   cd ../.. && python3 scripts/build_traits_db.py
   ```
8. Sonraki partiye dön (1. adım).

## ÖNEMLİ — model etiketi notu

`ingest_uretim.py` içinde çıktı dosyasını isimlendirirken model adı şu an
`claude-opus-5` olarak SABİT yazılı. Bu script değiştirilmeden çalıştırılırsa
senin ürettiğin kayıtlar da yanlışlıkla "claude-opus-5" diye etiketlenir.
Bunu düzeltmeden ingest_uretim.py'ı çalıştırma — kullanıcıya sor ya da
`MODEL = "claude-opus-5"` satırını kullandığın gerçek model adıyla değiştir
(örn. `"gpt-5.6-luna"`), her partiden önce kontrol et.

## Yapma

- Prompt şablonunu, etiket setini veya doğrulama kurallarını değiştirme.
- Pilot klasörlerine (`ciktilar/`, `ham/`, `degerlendirme.csv`) dokunma.
- `targets_production.json`'u yeniden üretme; sıralama sabit kalmalı.
- Sonucu yorumlama/özetleme, iddiaları kendin düzeltme/güzelleştirme. Ham veriyi
  olduğu gibi kaydet.
- Kendi kendine doğrulama adımını (Değişmez kural 6) atlama.

## Bekleyen ayrı iş (bilgi amaçlı, senin görevin değil)

`degerlendirme.csv` — kullanıcı elle dolduracak, `score.py` ile ölçülecek.
Değerlendirme LLM'e yaptırılmıyor; katı/objektif rubriklerle ölçülüyor. Bu görevde
buna dokunma.
