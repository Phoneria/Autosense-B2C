# Analiz referans verileri

Bu klasör B2C'nin bağımsız veri kopyalarını tutar. Büyük veritabanları Git'e eklenmez.

- `listings.sqlite3`: sadece `search_listing`; B2B kullanıcı, parola, oturum ve görev tabloları bulunmaz.
- `paket_fiyatlari.db`: mevcut fiyat motorunun paket referansları.
- `galeri.db`: sadece `galleries` ve `gallery_listings` tabloları.
- `import.json`: son aktarım zamanı ve kaynak klasör kaydı.
- `accounts.sqlite3`: yerel B2C hesapları; referans veri aktarımı bu dosyaya dokunmaz.
- `vehicle_traits.db`: araç kronik / iyi / kötü özellikleri. Diğerlerinden farklı
  olarak B2B'den aktarılmaz; `python3 scripts/build_traits_db.py` ile
  `research/kronik-pilot/ciktilar_uretim/B/*.json` çıktılarından üretilir.
  Yeni araç verisi üretildikten sonra sadece bu betiği çalıştırmak yeterlidir —
  backend dosyanın mtime'ına bakar, servisi yeniden başlatmaya gerek yoktur.
  Dosya yoksa özellik sessizce kapalı kalır, analiz çalışmaya devam eder.

`python3 scripts/import_reference_data.py /kaynak/Autosense` referansları yeniden oluşturur.
Kaynak veritabanları salt okunur açılır, hedefler geçici dosyada doğrulanıp atomik olarak değiştirilir.
Çalışan servisi veri güncellemesinden sonra yeniden başlatın. Aktarım otomatik veya günlük değildir.
Yayında referansları salt okunur mount edin; hesaplar ayrı PostgreSQL veritabanındadır.
