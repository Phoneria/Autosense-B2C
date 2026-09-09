# AutoSense B2C

Bağımsız React + Django uygulaması: e-posta ile kayıt, zorunlu e-posta doğrulama,
session-cookie girişi, parola sıfırlama ve korunan araç analizi. Ödeme/abonelik bu sürümde yoktur.

Kod ve analiz verileri Autosense'ten bu klasöre kopyalandı. Çalışmak için eski
projenin klasörüne, Python ortamına veya B2B kullanıcılarına bağımlı değildir.

## Yerelde başlatma

Python 3.12+ ve Node.js 22.12+ gerekir. Bu çalışma ortamında bağımlılıklar ve
referans verileri hazırdır:

```sh
./dev.sh
```

Uygulama: **http://localhost:5176**. Django sadece `127.0.0.1:8010` üzerinde çalışır;
tarayıcı istekleri Vite proxy üzerinden aynı origin'den gider. Ctrl+C iki servisi kapatır.

Yeni bir makinede önce `./setup.sh` çalıştırın. İsteğe bağlı yerel ayarlar için
`.env.example` dosyasını `.env` olarak kopyalayın; `dev.sh` yükler.
Doğrudan `manage.py` çağrılarında ortam değişkenlerini ayrıca export edin.

Yerel e-postalar **`.local/mail/`** içindeki özel izinli dosyalara yazılır; bu mod
gerçek e-posta göndermez. Doğrulama 6 haneli kodla yapılır: kayıttan sonra son
maildeki kodu doğrulama ekranına girin, ardından parolanızla giriş yapın.

```sh
grep -E '^[0-9]{6}$' "$(ls -t .local/mail/*.log | head -1)"
```

Kod 15 dakika geçerlidir, en fazla 3 deneme hakkı vardır ve kaydolduğunuz tarayıcı
oturumuna bağlıdır; oturum düşerse doğrulama ekranından yeni kod isteyin. Kodu girmek
bekleyen girişi de tamamlar: kod yalnızca parolayı giren oturumda girilebildiği için
allauth bunu kimlik kanıtı sayar ve kullanıcı doğrudan uygulamaya alınır.
Posta bağlantıları ve hesap veritabanları Git'e eklenmez.

## Proje yapısı

```text
frontend/           React, hesap ekranları ve mevcut analiz arayüzü
backend/accounts/   B2C hesap modeli, allauth adaptörü, izinler ve hesap testleri
backend/search/     Kopyalanan analiz motoru, katalog ve korunan API'ler
backend/config/     B2C'ye özel Django ayarları ve URL listesi
data/               Bağımsız analiz snapshot'ları (Git dışında)
e2e/                Gerçek tarayıcı akışları
deploy/             HTTPS proxy, Docker smoke ortamı ve geçiş notları
```

## Veri yönetimi

Yerel hesap veritabanı `data/accounts.sqlite3`; yayın ortamında ayrı PostgreSQL'dir.
Referanslar `data/listings.sqlite3`, `data/paket_fiyatlari.db`, `data/galeri.db`
dosyalarından salt okunur açılır. B2B kullanıcı, parola ve oturumları kopyalanmaz.

Veriler bağımsız snapshot'lardır; otomatik güncelleme yoktur. Yenilemek için:

```sh
python3 scripts/import_reference_data.py /tam/yol/Autosense
```

Ardından çalışan B2C servisini yeniden başlatın. Aktarım kaynakları değiştirmez,
B2C hesaplarını silmez ve yeni dosyaları bütünlük kontrolünden sonra yerleştirir.
İlk aktarımda kaynak `galeri.db` içindeki kullanılmayan `listing_descriptions`
tablosunda bozulma görüldü. Yalnızca gereken `galleries` ve `gallery_listings`
tabloları aktarıldı; yeni dosyanın bütünlük kontrolü geçti. Kaynak dosya onarılmadı.

## Testler

```sh
.venv/bin/pytest -q
npm --prefix frontend run build
npm run test:e2e
```

Tarayıcı testleri `.local/e2e/` altında ayrı hesap veritabanı ve e-posta kutusu
oluşturur; gerçek auth akışlarını ve kopyalanmış referanslarla analiz motorunu çalıştırır.
5176 ve 8010 portları boş olmalıdır. Test raporu `playwright-report/index.html`,
ekran görüntüleri `.local/screenshots/` altında oluşur.

## HTTPS ve yayın

Yerel yayın benzeri ortam, gerçek PostgreSQL/Redis ve Mailpit SMTP sunucusu kullanır:

```sh
sh deploy/https-smoke.sh
python3 deploy/https-smoke-check.py
npm run test:e2e:https
```

HTTPS: **https://localhost:8443**, test posta kutusu: **http://localhost:8026**.
Bu ortam yerel sertifika kullanır; otomatik kontrol `.local/smoke-ca.crt` ile
sertifikayı doğrular. Tarayıcı sistem güven deposuna bu sertifika otomatik eklenmez.

Canlı yayın için `.env.production.example` dosyasını `.env.production` olarak kopyalayıp
domain, ayrı secret/veritabanı parolası ve doğrulanmış SMTP göndericisini doldurun:

```sh
docker compose --env-file .env.production up --build -d
```

Caddy TLS sonlandırır, statik arayüzü sunar ve `/api/*` ile `/_allauth/*` yollarını
özel ağdaki B2C Django servisine yönlendirir. Backend, PostgreSQL ve Redis host portu
açmaz. Referans mount'u salt okunurdur. Django production ayarları eksik secret,
HTTPS, Redis veya SMTP yapılandırmasında başlamaz.

Canlı DNS/domain ve SMTP hesabı henüz yapılandırılmadı; canlı yayın yapılmadı.
Eski Autosense sunucusundaki açık B2C yolları da bu yeni klasör oluşturulunca
kendiliğinden kapanmaz. Yayın geçişinde `deploy/CUTOVER.md` adımlarını tamamlayın.

## Doğrulanan teslim

8 Eylül 2026: 74 backend testi, 3 yerel tarayıcı testi ve 1 HTTPS/SMTP tarayıcı
testi geçti. Gerçek referanslarla analiz, hasar seçimi, mobil görünüm, kayıt/giriş,
kullanılmış ve geçersiz bağlantılar, CSRF, çıkış ve parola sıfırlamasında oturum
iptali doğrulandı. Frontend build, migration kontrolü, Docker build ve HTTPS
proxy kontrolleri başarılı; frontend bağımlılık taraması 0 açık bildirdi.
