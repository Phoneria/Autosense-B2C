# Kronik / artı-eksi verisi — durum notu

Son güncelleme: 14 Eylül 2026

## Nerede kaldık

**Pilot (A vs B karşılaştırması) — üretim bitti, değerlendirme bekliyor.**
6 araç × 2 yöntem = 12 koşum tamam. `degerlendirme.csv` içinde 94 kronik iddia var,
`KARAR` sütunu boş. Doldurulunca `python3 score.py` objektif sayıları basar.

Otomatik ön sinyaller (elle değerlendirme öncesi):
- Şema ihlali 205 kaydın hiçbirinde yok
- Etiket örtüşmesi A∩B: popüler %62, uzun kuyruk %36
- B'nin kaynak türü: popülerde %83 kullanıcı forumu, uzun kuyrukta %33
- Güven kalibrasyonu: B uzun kuyrukta 24 iddianın 15'ini "düşük" işaretledi;
  A aynı yerde 22'nin sadece 2'sini. Kapalı kitap model nerede zayıf olduğunu bilmiyor.

**Üretim (B, 300 hedef) — 42/300 tamam.**
`targets_production.json` hazır (yaş filtresi yok, ilan sayısına göre ilk 300,
kapsam %48,4). Tamamlananlar `ciktilar_uretim/B/` altında, liste
`ciktilar_uretim/_durum.json` içinde.

42 hedefin sonucu: 704 kayıt (327 kronik, 199 iyi, 178 kötü), 0 şema ihlali, 0 boş hedef.
Son güncelleme 14 Eylül 2026.

## Siteye entegrasyon — TAMAM (14 Eylül 2026)

- `scripts/build_traits_db.py` → `data/vehicle_traits.db` (42 araç, 700 kayıt)
- `backend/search/services/vehicle_traits.py` — salt okuma, mtime ile kendini tazeler
- `GET /api/b2c/vehicle-traits` (liste) ve `?key=` (tek araç)
- `analyze()` çıktısında `vehicle_traits` alanı
- `frontend/src/components/VehicleTraits.tsx` — 12. kart, üstte araç seçim kutusu

Filtre eşikleri `build_traits_db.py` içindeki `FILTRE` bloğunda; şu an kapalı.
Değerlendirme bitince orayı düzenleyip betiği yeniden çalıştır — uygulama kodu
değişmez.

### Entegrasyon sonrası düzeltme

`ProtectedView` alt sınıfları `feature` özniteliği olmadan 403 döner.
`VehicleTraitsView`'da atlanmıştı; `feature = "vehicle_traits"` eklendi ve
`accounts/features.py::FEATURES` setine yazıldı. Backend yeniden başlatılmalı.

## Sıradaki adımlar

1. `degerlendirme.csv`'yi elle doldur (D/Y/K) → `score.py` → eşikleri belirle
2. Kalan 258 hedefi koştur. Yöntem: her hedef için
   `rendered_uretim/<id>.md` prompt'unu bir subagent'e ver, çıktıyı
   `ham_uretim/B/<id>.json` olarak yazdır, sonra doğrulamadan geçir.
   Prompt üretimi: `prompt_B_kaynakli.md` içindeki `{{ETIKETLER}}` ve `{{HEDEF}}`
   yer tutucularını doldur.
   Bir koşum ≈ 120k token, ≈ 50-80 web araması, 5-15 dakika.
3. Eşikler netleşince filtreyi uygula, `vehicle_traits.db`'yi üret
4. 12. analiz kartını bağla — veri yoksa kart hiç görünmesin

## Karar defteri

- Runtime'da LLM YOK. Üretim offline, tek seferlik; çalışma anında saf lookup.
- Kaynaksız iddia kabul edilmiyor (B yöntemi). A (kapalı kitap) sadece kontrol grubu.
- Değerlendirme LLM'e yaptırılmıyor — elle, sabit D/Y/K kodlarıyla.
- Araç yaşı filtresi yok; yaş sadece etiket, kart eşiği sonuç verisine bakılarak konacak.
- Üretim Claude subagent ile (abonelik kapsamında); `runner.py` API yolu tazeleme
  ve model karşılaştırması için duruyor.
