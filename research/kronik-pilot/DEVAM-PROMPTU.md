# AutoSense — kronik/artı-eksi verisi üretimi (devam görevi)

> Bu metni yeni bir Claude oturumuna olduğu gibi yapıştır.
> Ön koşul: `Autosense-B2C` klasörünün o oturuma bağlı olması.

---

Merhaba. Devam eden bir veri üretim işini sürdüreceksin. Aşağıdakileri
harfiyen uygula; kurallar keyfi değil, ölçümle konuldu.

## Bağlam

AutoSense B2C, Türkiye'de ikinci el araç ilanı için fiyat/pazarlık analizi veren
bir web uygulaması (Django + Vite). Analiz raporuna 12. kart olarak
**"bu motorun kronik arızaları + iyi/kötü yönleri"** ekleniyor.

Bu veri şu an üretiliyor: 300 hedef motorun **21'i tamam, 279'u kalıyor.**

## Değişmez kurallar

1. **Runtime'da LLM yok.** Bu üretim offline ve tek seferlik; ürün çalışırken
   sadece hazır veriye lookup yapacak. Ürünün temel farklılaştırıcısı
   tekrarlanabilir çıktı — bunu bozma.
2. **Kapalı kitap yasak.** Hiçbir iddia modelin hafızasından yazılmaz.
   Her iddia, gerçekten açılmış bir URL'ye dayanır.
3. **Uydurma URL yasak.** Açılamayan, 404 veren, aramada görülmeyen adres yazılmaz.
   Kaynak bulunamayan iddia hiç yazılmaz. Boş liste kabul edilebilir sonuçtur.
4. **Kapalı etiket seti.** `etiketler.json` dışında etiket üretilmez.
5. **Değerlendirmeyi LLM'e yaptırma.** Bu oturumda değerlendirme yok, sadece üretim.
   Kalite ölçümü ayrıca elle yapılıyor.

## Çalışma klasörü

```
research/kronik-pilot/
├─ targets_production.json     300 hedef (marka+seri+motor, ilan sayısına göre sıralı)
├─ prompt_B_kaynakli.md        prompt şablonu — DEĞİŞTİRME
├─ etiketler.json              kapalı etiket setleri — DEĞİŞTİRME
├─ dogrulama.py                şema doğrulama, tek doğruluk kaynağı
├─ render_prompts.py           sıradaki hedefler için prompt üretir
├─ ingest_uretim.py            ham çıktıları doğrular, temiz JSON yazar
├─ rendered_uretim/<id>.md     hazır promptlar
├─ ham_uretim/B/<id>.json      subagent'ın yazdığı ham çıktı
├─ ciktilar_uretim/B/<id>__claude-opus-5.json   doğrulanmış çıktı
└─ DURUM.md                    durum notu — iş bitince güncelle
```

Bu klasördeki dosyalar kullanıcının bilgisayarında. Okuma/yazma için `device_bash`
kullan (`$HOME/mnt/Autosense-B2C/research/kronik-pilot`). Konteynere kopyalama.

## Akış

### 1. Sıradaki partiyi hazırla

```bash
cd $HOME/mnt/Autosense-B2C/research/kronik-pilot
python3 render_prompts.py 13
```

Tamamlanmış hedefleri atlar, sıradaki 13 hedef için `rendered_uretim/<id>.md`
üretir ve listeler. Parti boyu 13 — daha fazlası zaman aşımı riskini artırıyor.

**Ama subagent konteynerde çalışıyor, prompt dosyaları kullanıcının makinesinde.**
Bu yüzden partinin prompt dosyalarını `device_stage_files` ile konteynere al;
staged yol `/mnt/user-data/uploads/...` altında olur, subagent'a o yolu ver.

### 2. Her hedef için bir subagent başlat

Parti içindeki 13 çağrıyı **tek mesajda** yap ki paralel koşsunlar.
`subagent_type: general-purpose`, `model: opus`. Prompt şablonu:

```
Read <staged prompt yolu> and follow it exactly.

You MUST use WebSearch/WebFetch; every claim needs a URL you actually opened.
Never invent a URL; omit unsourced claims (an empty list is acceptable).
Turkish owner forums and complaint sites are the best sources
(sikayetvar.com, forum.donanimhaber.com, marka forumları, eksisozluk).

Then Write the JSON to /mnt/user-data/outputs/<id>.json (pure JSON, no code fences).

Your final message must be ONE line with the counts, e.g. "8 kronik, 5 iyi, 4 kotu".
Do not repeat the JSON — it must not enter the parent context.
```

Son satır önemli: JSON'ı ana bağlama taşırsan oturum bütçesi çabuk biter.
Bir koşum ≈ 120k token, 50-80 web araması, 5-15 dakika sürüyor.

### 3. Çıktıları kullanıcının klasörüne yaz

Parti bitince `/mnt/user-data/outputs/<id>.json` dosyalarını
`device_commit_files` ile `.../research/kronik-pilot/ham_uretim/B/<id>.json`
yoluna yaz. Sonra doğrula:

```bash
cd $HOME/mnt/Autosense-B2C/research/kronik-pilot && python3 ingest_uretim.py
```

Bu komut `ciktilar_uretim/B/` altına temiz JSON'ları ve `_durum.json`'u yazar;
şema ihlali, boş dönen hedef ve kaynak alan adı dağılımını basar.
**Şema ihlali sıfırdan büyükse dur ve kullanıcıya bildir** — pilotta 205 kayıtta
sıfırdı, ihlal çıkması promptta bir şeyin bozulduğu anlamına gelir.

### 4. Partiyi raporla, devam et

Her parti sonunda kısa rapor: kaç hedef, kaç kayıt, ihlal var mı, boş dönen var mı.
Sonra 1. adıma dön. Oturum bütçesi dolduğunda `DURUM.md`'yi güncelle ve bırak.
Oturum başına ~90-110 koşum sığıyor.

## Kayıt şeması

```json
{
  "hedef_id": "renault-clio-1-5-dci",
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
- `etiket`: `etiketler.json` içindeki ilgili listeden, dışına çıkılamaz
- `km_araligi`: sadece kronikte ve biliniyorsa, yoksa `null`
- `guven`: `yuksek` (3+ bağımsız kaynak) | `orta` (2) | `dusuk` (1)
- Üst sınır: 8 kronik, 5 iyi, 5 kötü

`dogrulama.py` bunları otomatik denetler; uymayan kayıt `_gecersiz`e düşer ve
veriye girmez.

## Yapma

- Prompt şablonunu, etiket setini veya doğrulama kurallarını değiştirme.
  Değişiklik gerekiyorsa önce kullanıcıya sor — üretilmiş 21 hedefle tutarlılık bozulur.
- Pilot klasörlerine (`ciktilar/`, `ham/`, `degerlendirme.csv`) dokunma.
  Onlar ayrı bir ölçümün verisi.
- Subagent çıktısını ana bağlama taşıma.
- `targets_production.json`'u yeniden üretme; sıralama sabit kalmalı.
- Sonucu yorumlama/özetleme, iddiaları kendin düzeltme. Ham veriyi olduğu gibi kaydet.

## İlk iş

`python3 render_prompts.py 13 --liste` çalıştır, kalan hedef sayısını doğrula,
sonra ilk partiyi başlat.
