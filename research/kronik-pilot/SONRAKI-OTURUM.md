# AutoSense — kronik/artı-eksi işi: devir brief'i

> Bu metni yeni Claude oturumuna olduğu gibi yapıştır.
> Ön koşul: `Autosense-B2C` klasörü o oturuma bağlı olmalı.

---

Devam eden bir işi sürdüreceksin. İki ayrı hat var: **veri üretimi** (devam ediyor)
ve **siteye entegrasyon** (bitti, doğrulanmayı bekliyor).

## Ürün bağlamı

AutoSense B2C: Türkiye'de ikinci el araç ilanı için fiyat/pazarlık analizi veren
web uygulaması (Django + Vite). Analiz raporu 11 karttan oluşuyordu, 12. kart
olarak **"araca özel kronik arızalar + iyi/kötü yönler"** eklendi.

**Değişmez kural:** üründe runtime'da LLM yok. Veri offline üretilir, uygulama
sadece hazır veriye lookup yapar. Tekrarlanabilir çıktı ürünün temel
farklılaştırıcısı — bunu bozma.

## Hat 1 — Veri üretimi (42/300 tamam, 258 kaldı)

Tam yönerge: `research/kronik-pilot/DEVAM-PROMPTU.md` — önce onu oku, aynen uygula.

Özet akış:

```bash
cd $HOME/mnt/Autosense-B2C/research/kronik-pilot
python3 render_prompts.py 13        # sıradaki 13 hedefin promptunu üretir
# her hedef için bir subagent (general-purpose, opus), 13'ü TEK mesajda paralel
# subagent çıktıyı ham_uretim/B/<id>.json'a yazsın, son mesajı tek satır sayaç olsun
python3 ingest_uretim.py            # doğrular, ciktilar_uretim/B/ altına yazar
python3 ../../scripts/build_traits_db.py   # siteye yansısın diye
```

Kurallar: kaynaksız iddia yok, uydurma URL yok, kapalı etiket seti dışına çıkma.
Subagent çıktısını ana bağlama taşıma — bütçe oradan yanıyor.
Şema ihlali > 0 çıkarsa dur ve haber ver (şu ana kadar 700 kayıtta 0 ihlal).

## Hat 2 — Siteye entegrasyon (kod bitti)

Yeni/değişen dosyalar:

| Dosya | Ne yapar |
|---|---|
| `scripts/build_traits_db.py` | JSON çıktıları → `data/vehicle_traits.db`. Filtre eşikleri tepedeki `FILTRE` bloğunda, şu an KAPALI. |
| `backend/search/services/vehicle_traits.py` | Salt okuma. Bağlantı dosyanın mtime'ına bakar, servis yeniden başlatmadan tazelenir. |
| `backend/search/views.py` | `VehicleTraitsView` — `feature = "vehicle_traits"` |
| `backend/accounts/features.py` | `FEATURES`'a `vehicle_traits` eklendi |
| `backend/search/urls.py` | `GET /api/b2c/vehicle-traits` (liste) ve `?key=` (tek araç) |
| `backend/search/services/b2c.py` | `analyze()` çıktısına `vehicle_traits` alanı |
| `backend/config/settings.py` | `B2C_TRAITS_DB` |
| `frontend/src/components/VehicleTraits.tsx` | 12. kart: üstte araç seçim kutusu (markaya göre optgroup), altında kronik/iyi/kötü üç sütun yan yana |
| `frontend/src/types.ts`, `api.ts`, `components/Results.tsx`, `styles.css` | tip, istemci, yerleşim, stil |

Eşleşme **sadece tam marka+seri+motor** üzerinden; yaklaşık eşleştirme yok
(kronik arıza motora özgü, komşu motorun verisi yanlış bilgi olur).

### Doğrulanmayı bekleyen

1. **Backend yeniden başlatılmalı** — `features.py` ve `views.py` değişti.
2. Tarayıcıda kontrol: seçim kutusunda 42 araç markaya göre gruplu görünüyor mu,
   araç değiştirince liste yenileniyor mu, kaynak linkleri açılıyor mu.
3. `npm run build` bu repodaki `node_modules` macOS'ta kurulduğu için Linux VM'de
   çalışmıyor (rolldown native binding). Kullanıcının kendi makinesinde koşmalı.
   `npx tsc --noEmit` temiz.

### Bilinen tuzak

`ProtectedView` alt sınıflarında `feature` özniteliği YOKSA `FeaturePermission`
herkesi 403 ile reddeder. Yeni uç eklerken `feature` tanımlamayı ve
`accounts/features.py::FEATURES` setine eklemeyi unutma — bir kez atlandı,
seçim kutusu sessizce boş kaldı.

## Bekleyen asıl karar

`research/kronik-pilot/degerlendirme.csv` — 94 kronik iddia, `KARAR` sütunu boş.
Kullanıcı elle dolduracak (D = doğrulandı, Y = yanlış, K = teyit edilemedi),
sonra `python3 score.py`. Kriterler `README.md`'de.

Çıkan hata oranı `build_traits_db.py` içindeki `FILTRE` eşiklerini belirleyecek.
O eşikler konmadan üretilen veri ürüne olduğu gibi giriyor — üretime devam etmek
sorun değil, çünkü filtre sonradan uygulanıyor ve uygulama kodu değişmiyor.

**Değerlendirmeyi LLM'e yaptırma.** Kullanıcının açık kuralı: metrikler katı,
objektif rubriklerle ölçülür, LLM-as-a-judge değil.

## Yapma

- Prompt şablonunu, etiket setini, hedef sıralamasını değiştirme
- Pilot klasörlerine (`ciktilar/`, `ham/`, `degerlendirme.csv`) dokunma
- Token %90'a gelince dur, `DURUM.md`'yi güncelle, devret
