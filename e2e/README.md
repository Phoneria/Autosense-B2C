# Tarayıcı kabul testleri

Proje kökünden:

```sh
npm ci
npx playwright install chromium
npm run test:e2e
```

Önkoşullar: `.venv` içinde backend bağımlılıkları, `frontend/node_modules` ve README'de açıklanan analiz referans verileri hazır olmalı. Testler Django'yu 8010, Vite'ı 5176 portunda başlatır; bu portların boş olması gerekir. Test sunucuları tamamlanınca kapatılır.

Her çalıştırma yalnızca `.local/e2e/` içindeki geçici hesap veritabanını ve özel e-posta kutusunu yeniler. Geliştirme hesapları ve referans verileri değiştirilmez. Kayıt/doğrulama/sıfırlama gerçek allauth API'leri üzerinden çalışır; testler Django'nun gönderdiği MIME e-postadaki bağlantıları okur. Auth istekleri veya analiz yanıtları taklit edilmez. Oturum süresi testi, yalnızca geçici hesap veritabanındaki oturum tarihlerini geçmişe çeker.

Kapsam: kayıt, e-posta doğrulama, zorunlu parola ile giriş, HttpOnly cookie, sayfa yenileme, gerçek Fiat Egea analizi, çıkış ve sıfırlama sonrası eski oturumun reddi, yeni parola ile giriş, kullanılmış/geçersiz bağlantılar, mobil yatay taşma ve alan etiketleri, girişsiz yönlendirme, açık sayfada oturum bitişi.

HTML raporu `playwright-report/index.html` altında üretilir. Başarısız koşullarda ekran görüntüsü ve trace `test-results/` içine yazılır. Bu yerel testler gerçek SMTP teslimini veya üretim HTTPS/proxy yapılandırmasını doğrulamaz.

## Yerel HTTPS ve SMTP smoke testi

README’deki üretim benzeri Docker smoke stack (`https://localhost:8443`, Mailpit `http://localhost:8026`) çalışırken `npm run test:e2e:https` komutu kullanılır. Ayrı yapılandırma mevcut HTTPS servisine bağlanır; geçici varsayılan test sunucularını başlatmaz. Rastgele bir test hesabıyla SMTP teslimi, bağlantı doğrulama, Secure/HttpOnly/SameSite cookie, analiz ve çıkış doğrulanır. Yalnızca yerel smoke sertifikası için bu tarayıcı context’inde sertifika denetimi atlanır; gerçek sertifika zinciri ayrıca `deploy/https-smoke-check.py` tarafından smoke CA ile doğrulanır. E-postalar yerel Mailpit kutusuna gider.
