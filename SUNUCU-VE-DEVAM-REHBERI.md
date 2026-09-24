# AutoSense B2C — Sunucu ve Devam Rehberi

> Son güncelleme: 24 Eylül 2026
> Bu dosya iki soruya cevap veriyor: **şu ana kadar ne yaptık** ve **başka bir bilgisayara geçince ne yapmalıyım**.
> Bu dosyada **hiçbir şifre/anahtar yok**. Gizli bilgiler sadece sunucudaki `.env.production` dosyasında duruyor.

---

## 1. Genel resim

**Canlı site:** https://auto-sense.com.tr
Kapasite hedefi: aynı anda en fazla ~250 kullanıcı. Sunucu bunun için fazlasıyla yeterli.

```
Kullanıcı → auto-sense.com.tr
          → Cloudflare DNS  ("49.13.139.19'a git")
          → Hetzner sunucu: Caddy (HTTPS) → Django (backend) → Postgres + Redis
                                                  ↘ Resend (SMTP) → kullanıcının mail kutusu
```

| Servis | Ne işe yarıyor | Hesap / not |
|---|---|---|
| **Natro** | Domain'in kayıtlı olduğu yer (`auto-sense.com.tr`) | Kayıt sahibi Bengü Özbek. Tek görevi nameserver'ları Cloudflare'e yönlendirmek. **Yıllık yenileme: 19 Eylül 2027** (otomatik yenileme açık değil, unutma) |
| **Cloudflare** (Free) | DNS, yani domainin adres defteri | Hesap: izzet.ahmet216@… Nameserver'lar: `magnolia.ns.cloudflare.com`, `rustam.ns.cloudflare.com` |
| **Hetzner Cloud** | Sitenin çalıştığı sunucu | Proje: *Autosense*. Sunucu `ubuntu-8gb-fsn1-1`, CX33 (4 vCPU, 8 GB RAM, 80 GB), Falkenstein, IPv4 `49.13.139.19` |
| **Resend** (Free) | Doğrulama kodu ve şifre sıfırlama maillerini gönderiyor | Hesap: izzet.ahmet216. Domain `auto-sense.com.tr` doğrulanmış, bölge Ireland (eu-west-1). Ücretsiz plan: günde 100 / ayda 3.000 mail |
| **GitHub** | Kod deposu | https://github.com/Phoneria/Autosense-B2C |

### Cloudflare DNS kayıtları (hepsi **DNS only / gri bulut**)

| Tip | Ad | İçerik | Not |
|---|---|---|---|
| A | `auto-sense.com.tr` | `49.13.139.19` | Site |
| A | `www` | `49.13.139.19` | Site (www yönlendirmesi henüz Caddy'de yok, bkz. Yapılacaklar) |
| CNAME | `send` | `send.forge.rmta.net` | Resend |
| CNAME | `rsend` | Resend'in istediği değer | Resend |
| TXT | `resend._domainkey` | DKIM anahtarı | Resend |
| TXT | `_dmarc` | `v=DMARC1; p=none;` | Mail teslimatı için önerilir, eklendiyse |

**Proxy'yi (turuncu bulut) açma.** Caddy kendi SSL sertifikasını Let's Encrypt'ten alıyor, proxy açılırsa sertifika yenilemesi bozulabilir.

---

## 2. Kod yapısı (kısa)

```
frontend/            React + Vite (TypeScript). Build'i Caddy statik olarak sunuyor
backend/             Django + DRF + allauth
  accounts/          Hesaplar, planlar (basic / pro / premium), krediler, izinler
  search/            Analiz motoru, araç rehberi, bölgesel fırsatlar, il/ilçe
  search/data/tr_il_ilce.json   81 il / 973 ilçe (sabit liste)
  config/            settings.py, urls.py, wsgi.py (açılışta ısıtma)
data/                Referans veritabanları (~2.9 GB). GIT'TE YOK
deploy/Caddyfile     HTTPS + /api ve /_allauth yönlendirmesi
compose.yaml         Yayın ortamı: web (Caddy), backend, postgres, redis
Dockerfile           frontend-build, backend, web aşamaları
dev.sh / setup.sh    Yerel geliştirme
```

Planlar (`backend/accounts/billing.py`):
- **basic:** sadece analiz
- **pro:** + senaryolar, amortisman, tahmin detayı, araç rehberi, bölgesel fırsatlar
- **premium:** + benzer ilanlar, rehber model detayı, bölgesel ilan listeleri, kronik sorun kaynakları

**İlan linkleri sadece Premium'da görünür.** Backend, Premium olmayanlara link göndermiyor. Üç yer var: analizde benzer ilanlar, Bölgesel Fırsatlar'daki "İlana git" linkleri, kronik sorun kaynak linkleri.

---

## 3. Sunucu tarafı

### Yerleşim
- Kod: `/opt/autosense-b2c`
- Gizli ayarlar: `/opt/autosense-b2c/.env.production` (izin `600`). **Git'te yok, rsync ile de gitmez** (`--exclude '.env*'`).
- Postgres verisi (kullanıcı hesapları): Docker volume `accounts_data`
- Redis: volume `rate_limits`
- Caddy sertifikaları: volume `caddy_data`
- Rehber/bölgesel önbellek: volume `derived_cache` → konteynerde `/app/cache`

### `.env.production` içindeki anahtarlar (değerler sunucuda)
```
B2C_DOMAIN=auto-sense.com.tr
B2C_WORKERS=4
B2C_THREADS=4
B2C_ANALYSIS_CACHE_TTL=3600
B2C_SECRET_KEY=<rastgele>
B2C_DB_PASSWORD=<rastgele>
B2C_SMTP_HOST=smtp.resend.com
B2C_SMTP_PORT=587          # Hetzner 25 ve 465'i dışarı kapatıyor, 587 kullan
B2C_SMTP_USER=resend
B2C_SMTP_PASSWORD=<Resend API key>
B2C_SMTP_TLS=true
B2C_FROM_EMAIL="Autosense <noreply@auto-sense.com.tr>"
```
⚠️ `B2C_DB_PASSWORD`'ü **değiştirme**. Postgres ilk açılışta bu şifreyle kuruldu, değişirse backend veritabanına bağlanamaz.

### Sık kullanılan komutlar (sunucuda, `/opt/autosense-b2c` içinde)
```sh
# Durum
docker compose --env-file .env.production ps

# Loglar
docker compose --env-file .env.production logs -f backend
docker compose --env-file .env.production logs web | grep -iE "certificate|error" | tail

# Yeniden build + başlat (deploy)
docker compose --env-file .env.production up --build -d

# Sadece frontend değiştiyse
docker compose --env-file .env.production up --build -d web

# Django shell
docker compose --env-file .env.production exec backend python manage.py shell

# İl listesi kontrolü (81 dönmeli)
docker compose --env-file .env.production exec backend python manage.py shell -c "from search.services import b2c; print(len(b2c.load_locations(force=True)))"
```
**Her komutta `--env-file .env.production` ver.** Vermezsen compose değişkenleri bulamaz ve "required variable ... is missing" hataları basar.

### SSH ile ilgili hatırlatma
`ssh root@49.13.139.19` yaz, **`root@ubuntu-8gb-fsn1-1:~#` satırını görene kadar bekle**, sonra komutları yapıştır. Önceden yapıştırılan komutlar yutuluyor.
Mac komutlarını (rsync) sunucuda **değil**, Mac'in kendi terminalinde çalıştır.

---

## 4. Deploy (kod değişikliğini yayına alma)

**1) Geliştirme bilgisayarında** (proje klasöründe):
```sh
rsync -avz \
  --exclude node_modules --exclude .venv --exclude .git --exclude '.env*' \
  --exclude .local --exclude 'playwright-*' --exclude 'test-results*' \
  --exclude 'Claude outputs' --exclude research \
  ./ root@49.13.139.19:/opt/autosense-b2c/
```

**2) Sunucuda:**
```sh
cd /opt/autosense-b2c
chmod -R a+rX data          # ÖNEMLİ: her rsync'ten sonra
docker compose --env-file .env.production up --build -d
docker compose --env-file .env.production logs -f backend   # "Bölgesel fırsatlar hazır" görünce Ctrl+C
```

Neden `chmod`: Mac'teki `data/` dosyaları `-rw-------` izinli. Backend konteyneri ayrı bir kullanıcıyla (uid 10001) çalıştığı için bu izinlerle dosyaları okuyamıyor. Sonuç: il listesi "Yüklenemedi", analiz verisi boş.

**3) Kontrol:** Tarayıcıda Cmd+Shift+R. Ayrıca:
```sh
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://auto-sense.com.tr/api/b2c/analyze   # 401 olmalı
```

Not: Backend açılırken `warm_caches` çalışıyor (Araç Rehberi + Bölgesel Fırsatlar önbelleği). Veri değiştiyse ilk açılış 1-3 dk sürebilir ve bu sırada site kapalıdır. Veri değişmediyse birkaç saniye sürer.

---

## 5. Yeni bir bilgisayara geçince (kod yokken)

### 5.1 Gerekenler
- Git, Python 3.12+, Node.js 22.12+
- Sunucuya SSH erişimi (bkz. 5.2)

### 5.2 SSH anahtarı
Sunucuya şu an **eski Mac'in SSH anahtarıyla** giriliyor (şifre yok). Yeni bilgisayarda:
```sh
ssh-keygen -t ed25519 -C "yeni-pc"
cat ~/.ssh/id_ed25519.pub        # çıktıyı kopyala
```
Bu public key'i sunucuya eklemenin üç yolu var:
1. **Eski Mac hâlâ erişilebilirse:** eski Mac'ten `ssh root@49.13.139.19` ile gir, anahtarı `~/.ssh/authorized_keys` dosyasının sonuna ekle.
2. **Hetzner Console:** Sunucu → **Console** (tarayıcıda terminal açar) → root olarak gir → anahtarı `authorized_keys`'e ekle. Root şifresi bilinmiyorsa önce Sunucu → **Rescue → Reset root password**.
3. İleride kullanmak için Hetzner → **Security → SSH Keys** kısmına da ekle (sadece yeni sunucularda otomatik kullanılır).

Test: `ssh root@49.13.139.19 'docker --version'`

### 5.3 Kodu al
```sh
git clone https://github.com/Phoneria/Autosense-B2C.git
cd Autosense-B2C
```

### 5.4 Veriyi al (`data/` Git'te yok, ~2.9 GB)
En güncel kopya sunucuda duruyor:
```sh
rsync -avz --progress root@49.13.139.19:/opt/autosense-b2c/data/ ./data/
```

### 5.5 Yerelde çalıştır
```sh
./setup.sh      # ilk seferde: venv, pip, npm, playwright
./dev.sh        # frontend + backend
```
Terminaldeki adresi aç (5176 veya 5177). Yerelde mailler gönderilmiyor, `.local/mail/` içine yazılıyor:
```sh
grep -E '^[0-9]{6}$' "$(ls -t .local/mail/*.log | head -1)"
```

Mac'te `Cannot find native binding` (rolldown) hatası alırsan:
```sh
cd frontend && rm -rf node_modules && npm ci && xattr -cr node_modules && cd .. && ./dev.sh
```

### 5.6 Değişiklik yapıp yayına alma
Bölüm 4'teki deploy adımları, aynen.

---

## 6. Şu ana kadar yapılanlar (kronolojik)

**Altyapı**
1. Domain Natro'da alındı, nameserver'lar Cloudflare'e çevrildi.
2. Cloudflare'de A kayıtları Hetzner IP'sine yönlendirildi (DNS only).
3. Hetzner'de CX33 Ubuntu sunucu açıldı, Docker kuruldu.
4. Resend hesabı açıldı, domain Cloudflare'e "Auto configure" ile doğrulandı, API key oluşturuldu.
5. Proje rsync ile `/opt/autosense-b2c`'ye atıldı, `.env.production` oluşturuldu, `docker compose up`. Caddy SSL'i otomatik aldı.
6. Test edildi: kayıt → mail kodu → giriş çalışıyor, girişsiz analiz 401 dönüyor.

**Kod düzeltmeleri**
| Konu | Dosya | Ne yapıldı |
|---|---|---|
| Build kırılıyordu | `frontend/src/components/AccountMenu.tsx` | Kullanılmayan `user` değişkeni kaldırıldı (TS6133) |
| Hesabım menüsü boş görünüyordu | `frontend/src/styles.css` | `.topbar .account-nav button{color:#fff}` menü içindeki yazıları beyazlatıyordu. Daha spesifik bir kural eklendi |
| Parolayı göster | `frontend/src/pages/AuthPages.tsx` | Parola alanlarına Göster/Gizle butonu eklendi |
| "Doğrulama e-postasını yeniden gönder" | `AuthPages.tsx` | Giriş ekranından kaldırıldı. Kod ekranında "Yeni kod gönder" zaten var |
| İl/ilçe "Yüklenemedi" | sunucu `chmod` + `backend/search/services/b2c.py` | Asıl sebep veri dosyası izinleriydi. Ayrıca il listesi okunamazsa sayfanın çökmemesi sağlandı |
| Eksik ilçeler (ör. Ezine) | `backend/search/data/tr_il_ilce.json` + `b2c.py` | Liste eskiden sadece galeri verisinden geliyordu (72 il / 320 ilçe). Artık 81 il / 973 ilçe temel alınıyor. Kaynak: github.com/snrylmz/il-ilce-json (2023 ADNKS) |
| Analizde 500 hatası | `b2c.py` | `NameError: rows` düzeltildi (`gallery_matches` artık `galeri_groups`'tan hesaplanıyor) |
| Footer altında beyaz boşluk | `AnalysisPage.tsx` + `styles.css` | `.app-shell` / `.app-main` sarmalayıcı, footer her zaman ekranın dibinde |
| Rehber/Bölgesel yavaş açılıyordu | `Dockerfile`, `compose.yaml`, `config/wsgi.py`, `search/management/commands/warm_caches.py` | Önbellek yazılabilir bir volume'a (`/app/cache`) taşındı, açılışta bir kez hesaplanıyor |

---

## 7. Yapılacaklar / açık konular

- [ ] **Bu değişiklikleri Git'e commit + push et.** Şu an sadece geliştirme Mac'inde ve sunucuda duruyorlar. Yeni PC'de `git clone` yapınca gelmeleri için bu şart.
- [ ] **Veritabanı yedeği:** Kullanıcı hesapları sadece sunucudaki Postgres'te duruyor. En kolay çözüm Hetzner → Sunucu → **Backups**'ı açmak (sunucu fiyatının %20'si). Alternatif: günlük `pg_dump` cron.
- [ ] **www yönlendirmesi:** `www.auto-sense.com.tr` Caddy'de tanımlı değil. `deploy/Caddyfile`'a `www.{$B2C_DOMAIN}` → ana domaine redirect eklenmeli.
- [ ] **Sunucu reboot:** "System restart required" uyarısı var. `apt upgrade` sonrası `reboot` yapılmalı, container'lar kendiliğinden kalkar (`restart: unless-stopped`).
- [ ] **Resend API key:** Şu anki key "Full access". Sadece "Sending access" + `auto-sense.com.tr` domainli bir key ile değiştirip `.env.production`'ı güncellemek daha güvenli.
- [ ] `backend/search/data/il-ilce-kaynak.json` gereksiz, silinebilir. Asıl kullanılan `tr_il_ilce.json`.
- [ ] Natro domain otomatik yenilemeyi aç (bitiş: 19 Eylül 2027).
- [ ] Referans verisi güncelleme süreci: `scripts/import_reference_data.py` → rsync → `chmod` → `up --build -d`.

---

## 8. Sorun giderme

| Belirti | Olası sebep / çözüm |
|---|---|
| `required variable ... is missing` | `--env-file .env.production` eksik |
| `no configuration file provided` | `/opt/autosense-b2c` içinde değilsin |
| İl listesi "Yüklenemedi", analiz verisi boş | `chmod -R a+rX data` yapılmamış |
| Frontend build `TS6133` vb. hata | Yerelde `cd frontend && node node_modules/typescript/bin/tsc -b` ile önceden kontrol et |
| Mail gelmiyor | Resend → Emails/Logs sayfasına bak. `docker compose ... logs backend \| grep -iE "smtp\|mail"` |
| Site açılmıyor | `docker compose ... ps` ile servislerin durumuna, `logs web` ile Caddy sertifika hatalarına bak. Cloudflare'de proxy'nin kapalı olduğunu kontrol et |
| SSH şifre soruyor | Komutu yanlış makinede çalıştırıyorsun (rsync sunucuda değil Mac'te), ya da o bilgisayarın anahtarı sunucuya eklenmemiş (bkz. 5.2) |
