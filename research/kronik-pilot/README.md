# Kronik / artı-eksi pilotu

**Amaç:** "LLM'e doğrudan sorsak olur mu?" sorusunu tahminle değil **ölçerek** cevaplamak.
İki yöntem aynı 20 araç üzerinde yarışır, fark tek değişkende: **kaynak zorunlu mu değil mi.**

- **A — kapalı kitap:** web araması yok, model sadece bildiğini yazar
- **B — kaynaklı:** her iddia, modelin gerçekten açtığı bir URL'ye dayanmak zorunda

Ölçüm **elle** yapılır. LLM'e puanlatmak yok — ölçtüğümüz şey LLM'in kendisi.

## Dosyalar

| Dosya | Ne işe yarar |
|---|---|
| `build_targets.py` | 20 hedef aracı DB'den seçer (deterministik) |
| `runner.py` | A ve B'yi 20 hedef üzerinde koşturur, çıktıları kaydeder |
| `targets_pilot.json` | Seçilen 20 araç: 10 popüler + 10 uzun kuyruk |
| `etiketler.json` | Kapalı etiket setleri — model bunun dışına çıkamaz |
| `prompt_A_kapali_kitap.md` | A yöntemi promptu |
| `prompt_B_kaynakli.md` | B yöntemi promptu |
| `ciktilar/A/`, `ciktilar/B/` | Model çıktıları: `<hedef_id>.json` |
| `make_sheet.py` | Çıktıları tek CSV'ye çevirir (kör sıralı) |
| `degerlendirme.csv` | **Elle doldurulacak dosya** |
| `score.py` | Doldurulmuş CSV'den objektif sayıları basar |

## Akış

1. `python3 build_targets.py` → hedefler hazır (zaten çalıştırıldı)
2. Koşum:
   ```bash
   export OPENAI_API_KEY=sk-...
   export PILOT_MODEL=gpt-6-astra        # opsiyonel, varsayılan bu
   python3 runner.py --limit 1           # önce tek hedefle dene
   python3 runner.py                     # 20 hedef × 2 yöntem
   ```
   Çıktılar `ciktilar/<A|B>/<hedef_id>.json`. Var olan dosyalar atlanır, yarıda
   kalırsa kaldığı yerden devam eder (`--yeniden` üzerine yazar).
3. `python3 make_sheet.py` → `degerlendirme.csv`
   **Bu turda sadece `kronik` iddialar CSV'ye giriyor.** İyi/kötü kayıtları yine
   üretiliyor ama puanlanmıyor: risk kronik tarafında. "Bagajı küçük" yanlışsa kimse
   zarar görmez, "şanzımanı patlar" yanlışsa ürün yanar. Hepsini almak için
   `python3 make_sheet.py --hepsi`.
4. CSV'de `KARAR` sütununu elle doldur (aşağıdaki kurallar)
5. `python3 score.py` → sayılar

### Kör değerlendirme

CSV'de `yontem` sütunu **en sona** konuldu ve satırlar karıştırıldı. Doldururken o sütunu
gizle. Hangi iddianın A'dan hangisinin B'den geldiğini bilirsen kendi beklentini
sonuca yazarsın — o zaman ölçüm değil, onay arama olur.

## KARAR kuralları (objektif)

Her iddia için **tek harf**:

**D — doğrulandı.** Modelin çıktısından bağımsız en az bir kaynakta teyit edildi.
Geçerli teyit sayılanlar:
- marka/model forumunda **aynı şikayeti anlatan en az 2 ayrı kullanıcı**
- teknik servis bülteni veya resmi geri çağırma kaydı
- o araca bakan bir ustanın doğrulaması

"Bana mantıklı geldi" teyit değildir.

**Y — yanlış.** Şunlardan biri varsa:
- iddia aracın teknik gerçeğiyle çelişiyor (zincirli motora "triger kayışı kopar" demek,
  manuel-only bir motora "DSG mekatronik arızası" demek)
- bulunan kaynak iddianın **tersini** söylüyor
- bahsedilen parça o araçta **yok**

**K — teyit edilemedi.** Arandı, ne doğrulandı ne çürütüldü.

> **K, D değildir.** Ürüne koyamayacağın bilgidir. Yüksek K oranı, düşük Y oranı kadar kötüdür —
> yanlış değil ama işe de yaramaz.

### B için ek iki sütun

- `URL_ACILIYOR` — E / H. Adres açılıyor mu? **H = uydurma URL.**
- `URL_DESTEKLIYOR` — E / H. Açılıyorsa, sayfa gerçekten o iddiayı söylüyor mu?

Bu iki sütun grounding'in gerçekten çalışıp çalışmadığını ölçer. Model URL uyduruyorsa
B yöntemi A'dan farksızdır, sadece daha pahalıdır.

## Karar eşikleri (öneri — kesinleştirilecek)

`score.py` çıktısındaki **YANLIS** sütununa göre:

| Yanlış oranı | Sonuç |
|---|---|
| ≤ %5 | Yöntem tek başına kullanılabilir |
| %5 – %15 | Sadece insan onay kuyruğuyla kullanılabilir |
| > %15 | O katmanda kullanılamaz |

Ek kurallar:

- **B'de uydurma URL oranı > %10** → grounding çalışmıyor. Prompt veya araç değişmeli,
  sonuçlar geçersiz.
- **Popüler ile uzun kuyruk arasındaki yanlış oranı farkı > 2 kat** → yöntemi sadece
  popüler katmanda kullan, uzun kuyruk için başka kaynak (YouTube/forum hattı) gerekir.
- **D oranı < %40** → yanlış az olsa bile çıktı ürüne koyacak kadar dolu değil.

## Hedef seçimi nasıl yapıldı

- Kaynak: `data/paket_fiyatlari.db` (yapısal marka/seri/motor) + `data/galeri.db` (ilan frekansı)
- Sadece `otomobil` ve `arazi-suv-pick-up` — ticari araçlar pilotta yok
- **Medyan ilan yılı ≤ 2020.** 2-3 yaşındaki aracın kroniği henüz oluşmamıştır;
  onu listeye koymak testi bozar, çünkü doğru cevap "bilinmiyor"dur ve bunu ne model
  ne usta bilebilir.
- Popüler: ilan sayısına göre en üstten, her marka+seriden en fazla 1 tane
- Uzun kuyruk: 5–150 ilan aralığından eşit aralıklarla, her markadan en fazla 1 tane


## runner.py'nin otomatik yaptığı kontroller

Elle kontrol yükünü azaltmak için üç şey koşum sırasında makine tarafından yapılıyor:

**1. Şema doğrulama.** Kapalı etiket setinde olmayan etiket, 140 karakteri aşan iddia,
B'de kaynaksız kayıt, A'da kaynaklı kayıt, tip başına üst sınırı aşan kayıt — hepsi
`_gecersiz` listesine ayrılıyor ve CSV'ye hiç girmiyor. **Bu sayının kendisi bir ölçüm:**
modelin verilen kurallara uyup uymadığını gösterir.

**2. Araç dışı URL tespiti.** B'de `web_search` aracının gerçekten getirdiği URL'ler
yanıtın `url_citation` ek açıklamalarından okunuyor. Modelin `kaynak_url` alanına yazdığı
adres bu listede yoksa kayıt `_arac_sonucunda_var: false` ile işaretleniyor — büyük
ihtimalle uydurma. Koşum sonunda toplamı da basılıyor.

**3. Ham yanıt saklama.** JSON ayrıştırılamazsa `<hedef_id>.ham.txt` olarak kaydediliyor,
ne olduğu kaybolmuyor.

Bunlar elle yapılan D/Y/K kararının yerine geçmez, sadece ön eleme yapar.

## A ve B neden aynı kod yolundan geçiyor

`runner.py` içinde A ile B arasındaki **tek fark** API çağrısındaki `tools` alanı:
A'da yok, B'de `web_search` var. Prompt şablonu, ayrıştırma, doğrulama, kayıt — hepsi
aynı. Başka bir fark (farklı model, farklı sıcaklık, farklı çıktı şeması) testi
geçersiz kılar, çünkü o zaman ölçtüğümüz şey "kaynak zorunluluğu" olmaktan çıkar.
