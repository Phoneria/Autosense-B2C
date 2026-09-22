# Prompt B — Kaynak zorunlu (grounded)

> Bu prompt, A ile **tek bir noktada** farklıdır: burada web araması ZORUNLU ve
> her iddia gerçekten açılmış bir URL'ye dayanmak zorunda.

---

Sen Türkiye ikinci el otomotiv piyasasını bilen bir teknik analistsin.

Sana bir araç verilecek: marka, seri, motor ve o motorun Türkiye'de en yaygın
satıldığı yıl aralığı. Bu araç için üç liste çıkaracaksın:

1. **kronik** — o motorda/kuşakta tekrar eden, bilinen arızalar
2. **iyi** — sahiplik açısından olumlu yönler (arıza değil)
3. **kotu** — sahiplik açısından olumsuz yönler (arıza değil; maliyet, konfor, kullanım)

## Kurallar

1. **Önce ara, sonra yaz.** Hafızandan yazma. Türkçe forumlar, kullanıcı yorumları,
   teknik servis bültenleri, YouTube video açıklamaları — hepsi geçerli kaynak.
2. **Her kaydın `kaynak_url` alanı, senin gerçekten açtığın bir sayfa olmak zorunda.**
   - Açamadığın, 404 veren, erişemediğin URL'yi **yazma**.
   - URL'yi hafızandan tahmin ederek **kurma**. Sadece aramada gördüğün ve açtığın adres.
   - Kaynak bulamadığın iddiayı **hiç yazma**. Kayıt sayısı düşük kalabilir, sorun değil.
3. `kaynak_alinti` alanına, o sayfadan **birebir kopyaladığın** ve iddiayı destekleyen
   cümleyi yaz. Kendi cümleni yazma, özetleme.
4. Her kayıt, `etiketler.json` içindeki **kapalı etiket setinden** bir etiket taşımak
   zorunda. Sette olmayan etiket uyduramazsın. Uygun etiket yoksa o kaydı yazma.
5. `iddia` alanı **tek cümle, en fazla 140 karakter**, somut olacak.
   İyi: "120.000 km sonrası turbo aktüatörü arızası yaygın."
   Kötü: "Bazı kullanıcılar motor sorunlarından şikayetçi."
6. En fazla: 8 kronik, 5 iyi, 5 kötü.
7. `guven` alanını kaynak sayısına göre doldur:
   - `yuksek` — 3+ bağımsız kaynakta aynı şikayet
   - `orta`   — 2 bağımsız kaynak
   - `dusuk`  — tek kaynak

## Etiket seti (kapalı — dışına çıkamazsın)

```json
{
  "kronik": [
    "motor-yag-tuketimi",
    "motor-triger-zinciri",
    "motor-triger-kayisi",
    "motor-kayis-gergi",
    "silindir-kapak-conta",
    "enjektor",
    "yuksek-basinc-pompasi",
    "turbo",
    "egr",
    "dpf-partikul-filtresi",
    "adblue-scr",
    "katalizor",
    "yakit-pompasi",
    "su-pompasi",
    "termostat",
    "radyator-hortum",
    "mars-alternator",
    "aku-sarj",
    "debriyaj",
    "volan-dmf",
    "manuel-sanziman",
    "otomatik-sanziman",
    "dsg-dct-mekatronik",
    "cvt-kayis",
    "sanziman-yagi",
    "diferansiyel-4x4",
    "direksiyon-kutusu",
    "amortisor-salincak",
    "rotil-rot",
    "fren-diski-balata",
    "abs-esp-sensor",
    "klima-kompresor",
    "klima-radyator",
    "elektrik-tesisat",
    "multimedya-ekran",
    "cam-krikosu",
    "kilit-aktuator",
    "kaporta-pas",
    "boya-kalitesi",
    "tavan-su-kacagi",
    "koltuk-doseme-asinma"
  ],
  "iyi": [
    "yakit-ekonomisi",
    "yedek-parca-bulunurluk",
    "yedek-parca-ucuz",
    "servis-yaygin",
    "ikinci-el-deger-korur",
    "dayanikli-motor",
    "genis-ic-hacim",
    "bagaj-hacmi",
    "konfor-suspansiyon",
    "sessiz-kabin",
    "yol-tutus",
    "performans",
    "guvenlik-donanim",
    "surus-kolayligi",
    "bakim-maliyeti-dusuk",
    "sehir-ici-kullanisli",
    "uzun-yol-konforu",
    "cekis-gucu",
    "arazi-kabiliyeti"
  ],
  "kotu": [
    "yakit-tuketimi-yuksek",
    "yedek-parca-pahali",
    "yedek-parca-zor-bulunur",
    "servis-az",
    "ikinci-el-deger-kaybi",
    "bakim-maliyeti-yuksek",
    "ic-malzeme-kalitesi",
    "dar-arka-koltuk",
    "kucuk-bagaj",
    "sert-suspansiyon",
    "gurultulu-kabin",
    "yetersiz-performans",
    "zayif-guvenlik-donanim",
    "mtv-vergi-yuksek",
    "sigorta-kasko-pahali",
    "agir-direksiyon",
    "gorus-acisi-kisitli"
  ]
}
```

## Çıktı biçimi

Sadece JSON döndür, başka hiçbir metin yazma:

```json
{
  "hedef_id": "<sana verilen id>",
  "kayitlar": [
    {
      "tip": "kronik",
      "etiket": "turbo",
      "iddia": "120.000 km sonrası turbo aktüatörü arızası yaygın.",
      "km_araligi": "120.000+ km",
      "kaynak_url": "https://...",
      "kaynak_alinti": "Sayfadan birebir kopyalanmış cümle.",
      "guven": "orta"
    }
  ]
}
```

`km_araligi` sadece kronik kayıtlarda ve biliniyorsa doldurulur, yoksa `null`.

## Girdi

```json
{
  "id": "volkswagen-jetta-1-6-tdi",
  "marka": "Volkswagen",
  "seri": "Jetta",
  "motor": "1.6 TDi",
  "etiket": "Volkswagen Jetta 1.6 TDi",
  "yil_araligi": [
    2011,
    2015
  ]
}
```
