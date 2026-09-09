# AutoSense B2C

Son kullanıcıya yönelik, giriş gerektirmeyen tek sayfalık araç analizi arayüzü.
Vite + React 19 + TypeScript. B2B panelinden (`frontend/`) tamamen ayrıdır:
kendi build'i, kendi deploy'u vardır ve Django'ya ayrı bir origin'den bağlanır.

## Çalıştırma

```bash
cd B2C
npm install          # ilk seferde
npm run dev          # http://localhost:5175
```

Backend'in ayrı bir terminalde ayakta olması gerekir:

```bash
cd Backend && source venv/bin/activate && python manage.py runserver
```

API adresi `VITE_API_URL` ile değiştirilir (varsayılan `http://127.0.0.1:8000/api`).
Örnek için `.env.example` dosyasına bakın.

```bash
npm run build        # dist/ -- statik SPA, herhangi bir statik host'a atılabilir
```

## Backend sözleşmesi

Bu uygulama beş endpoint kullanır. Sözleşme `src/types.ts` içinde tiplenmiştir;
kaynağı `Backend/search/services/b2c.py` ve `Backend/search/views_b2c.py`.

| Endpoint | Ne döner |
|---|---|
| `GET  /api/arabam-vehicles` | Marka / seri / motor / paket hiyerarşisi |
| `POST /api/b2c/lookup-text` | B2B ile aynı ilan metni ayrıştırıcısı; giriş gerektirmez |
| `GET  /api/b2c/locations` | İl ve ilçe listesi |
| `POST /api/b2c/vehicle-defaults` | Seçilen araç için vites varsayılanı |
| `POST /api/b2c/analyze` | Tam analiz |

**İl ve ilçe zorunlu değildir.** Ne formda ne de backend'de doğrulanır; bölge
yalnızca bölgesel fiyat sinyalini ve renk primini zenginleştirir. Bu bilinçli bir
karardır, düzeltilmesi gereken bir eksik değil.

## Geçmiş

Bu klasör önceden ChatGPT/Codex "Sites" projesinde üretilmiş bir Next.js + vinext
uygulamasının **derlenmiş çıktısını** barındırıyordu; kaynak kodu hiç bu repoda
olmadı. 2026-09-03'te uygulama aynı tasarımla (CSS birebir taşındı) Vite + React
olarak yeniden yazıldı. Önceki build referans olsun diye `_onceki_build/` altında
duruyor ve gitignore'ludur — yeni sürüm doğrulandıktan sonra silinebilir.

Yeniden yazımda eklenenler:
- İlan açıklaması alanı ve metinden anlam çıkarımı (çelişki tespiti dahil)
- İlan kalite puanına açıklama sinyallerinin katılması
- Fiyat trendinin bar grafikten çizgi grafiğe çevrilmesi (hover + crosshair)
- Yayındaki benzer ilanların listelenmesi

Formun üstündeki **İlan metninden otomatik doldur** alanına arabam.com veya
sahibinden.com ilan sayfasının tamamını yapıştırıp **Metinden doldur** düğmesine
basın. Marka, seri, motor, paket, yıl, km, vites ve hasar bilgileri doldurulur.
Fiyat ve ilan açıklamasını ayrıca girip alanları kontrol ederek analizi başlatın.
