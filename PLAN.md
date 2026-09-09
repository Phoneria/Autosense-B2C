# B2C hesap ve erişim altyapısı planı

Durum: Bağımsız uygulama kodlandı; 74 backend testi, 3 yerel tarayıcı testi ve 1 HTTPS/SMTP tarayıcı testi geçti. Canlı domain/SMTP kurulumu ve eski B2C yollarının kapatılması yayın geçişinde tamamlanacak.

## Kapsam

- Yalnızca B2C; mevcut B2B hesapları ve giriş akışı ayrı kalır.
- Yeni B2C kullanıcıları sıfırdan kayıt olur; kullanıcı taşıma yoktur.
- İlk açılışta login/signup; doğrulanmış oturumdan sonra mevcut B2C özellikleri açılır.
- Ödeme sağlayıcısı entegrasyonu, checkout, webhook, fiyatlar ve abonelik ekranları bu çalışmanın dışındadır. Ödeme aşaması sonraya bırakılmıştır.
- Premium özellikler henüz belirlenmedi; mevcut özellikler doğrulanmış kullanıcılara açık kalır.

## 1. Kaynak ve çalışma ortamı sınırını kesinleştir

Bağımsız proje Autosense-B2C/ altında çalışır. Kaynak kod Autosense/B2C ve gerekli analiz modüllerinden kopyalanır; frontend/ ve backend/ yeni çalışma kaynaklarıdır. Autosense içindeki B2B uygulaması korunur. Son yerel incelemede Autosense B2C/ klasörü bulunmadı. Canlı build/deploy kaynağı henüz doğrulanmadı; yayın öncesinde kullanılan kaynak klasör, branch ve domain kaydedilecek. İki kopyaya paralel değişiklik yapılmayacak. Uygulama yolları frontend/ ve backend/ altındadır; geçmiş B2C/ ve Backend/ adları kaynak projeyi tarif eder.

Karar: B2C için ayrı Django servisi, çalışma ayarları, kullanıcı veritabanı, session cookie, secret ve URL yapılandırması kullanılacak. Servis aynı sunucuda çalışabilir. Analiz servisleri yeniden kullanılır; B2B hesap ve iş endpoint'leri B2C URL yapılandırmasına dahil edilmez. Kullanıcı kimliği yalnızca farklı bir URL önekiyle ayrılmış sayılmaz.

B2C hesapları, doğrulama kayıtları ve oturumları ayrı veritabanında tutulur. Analiz referans verileri mevcut kaynaktan salt okunur alınır; kullanıcının bağımsız proje talebi doğrultusunda yalnızca gereken tablolarla kopyalanır; kaynak veriler silinmez. Mevcut Listing.objects sorguları dahil tüm veri erişimleri envantere alınarak B2C servisinde açık veritabanı yönlendirmesi veya veri erişim katmanı uygulanır. Referans veritabanında yazma ve migration engellenir; hesap sorguları bu kaynağa yönlendirilmez. Dosya tabanlı analiz kaynaklarına erişim de korunur. Ayrı servis çalıştırmaya engel bir yayın kısıtı çıkarsa kimlik izolasyonu kararı uygulamadan önce yeniden değerlendirilir.

Teslim: Aktif kaynak, ayrı B2C ayarları/veritabanı ve test ortamı; desteklenen Django sürümü ile uyumlu sabitlenmiş bağımlılıklar.

## 2. Oturum ve yayın mimarisi

- django-allauth headless browser API + Django sunucu oturumu.
- B2C DRF ayarlarında SessionAuthentication açıkça tanımlanır; mevcut B2B JWT authentication ayarları korunur. B2C iş uçları ayrıca aktif ve e-postası doğrulanmış kullanıcı permission'ı uygular.
- B2C sayfası, /api/ ve allauth yolları aynı origin altında reverse proxy ile sunulur. Mevcut farklı-origin doğrudan API çağrıları buna göre değişir.
- Geliştirmede Vite proxy; yayında karşılığı olan proxy yapılandırması.
- B2C domainindeki /api/ ve allauth yolları ayrı B2C Django servisine yönlendirilir. Mevcut Cloudflare Worker yayınının kaynak ve domain bilgileri doğrulanarak proxy karşılığı hazırlanır; cookie, CSRF ve HTTPS başlıklarının iletimi yayın benzeri ortamda test edilir.
- HTTPS, HttpOnly/Secure oturum cookie'si, SameSite=Lax, host kapsamlı ayrı cookie adı.
- Yazma isteklerinde CSRF; giriş endpoint'leri de korunur. CSRF token'ının frontend'e iletilmesi ayrı bootstrap sözleşmesiyle sağlanır.
- Oturum kimlikleri localStorage'a yazılmaz. Oturum ve auth yanıtları CDN'de cache'lenmez.
- Çıkış ve parola sıfırlaması sonrasında eski oturumların geçersizliği test edilir.

Teslim: Tarayıcı yenilemesinde oturum devam eder, çıkış sonrası korunan API erişimi kapanır.

## 3. Backend hesap akışları

- E-posta + parola ile kayıt ve giriş; kullanıcı adı zorunlu değil.
- E-posta normalizasyonu ve veritabanında büyük/küçük harf farkıyla mükerrer hesabın önlenmesi; parola doğrulayıcıları ve güvenli hash.
- Allauth zorunlu mail doğrulaması, süreli ve tek kullanımlık bağlantı.
- Doğrulama bekleme, yeniden mail gönderme, parola unutma ve sıfırlama.
- Kullanıcı aktifliği ile mail doğrulanmışlığı ayrı anlam taşır; yönetici onayı akışı kullanılmaz.
- Giriş, kayıt, parola sıfırlama ve mail tekrar gönderme için hesap/IP bazlı hız sınırları; kullanıcı varlığını gereksiz ifşa etmeyen yanıtlar.
- Allauth işlemleri yeniden yazılmaz; frontend adaptörü kütüphanenin belgelenmiş uçlarına bağlanır.
- Uygulama hesabı için /api/b2c/me: kimlik ve sunucuda hesaplanmış özellik yetkileri. Parola/hash veya gizli alan dönmez.

Dosya alanları: backend/config ayarları, kök urls.py, B2C hesap uygulaması (adapters.py, permissions.py, views.py, urls.py), migrations ve tests.

## 4. Mail gönderimi

- SMTP ayarları ortam değişkenlerinde; gerçek anahtarlar kaynak koduna girmez.
- Yerelde test mail kutusu veya console backend; yayında doğrulanmış gönderici alan adı.
- Türkçe doğrulama ve parola sıfırlama şablonları; bağlantılar B2C adresine gider.
- Gönderim hataları görünür ve takip edilebilir olur; gizli token'lar loglanmaz. Yeniden gönderme ile kullanıcı akışı kurtarılabilir.
- Başarılı doğrulama sonrası giriş ekranına yönlendirme; mail linki tek başına kalıcı uygulama oturumu açmaz.

## 5. Frontend ekran ve oturum altyapısı

- Mevcut src/App.tsx analiz ekranı pages/AnalysisPage.tsx içine ayrılır; App yönlendirmeyi yönetir.
- Eklenecek ekranlar: LoginPage, SignupPage, VerifyEmailPage, ForgotPasswordPage, ResetPasswordPage.
- Eklenecek modüller: auth/AuthProvider.tsx, auth/RequireAuth.tsx, auth/api.ts, auth/types.ts.
- src/api.ts: ortak cookie/CSRF yönetimi, tiplenmiş hata sınıfları; oturumsuzluk, doğrulama gereği, yetkisizlik ve hız sınırı ayrı işlenir. Her 403 yanıtı otomatik çıkış sayılmaz.
- Oturum yüklenirken uygulama ekranı ve analiz istekleri başlamaz.
- / doğrudan açıldığında oturum yoksa login; doğrulanmışsa analiz ekranı.
- Üst alanda hesap e-postası ve çıkış. Yenileme, doğrudan URL açma ve güvenli uygulama içi geri yönlendirme desteklenir.
- Türkçe, mobil uyumlu formlar; etiketler, klavye erişimi, işlem/hata/başarı durumları ve parola yöneticisi uyumu.

Dosya alanları: frontend/src/App.tsx, src/api.ts, src/styles.css, src/pages/, src/auth/, package.json, vite.config.ts.

## 6. B2C API erişimini kapat

- B2C iş uçlarında doğrulanmış ve aktif kullanıcı zorunlu permission uygulanır; sadece IsAuthenticated yeterli sayılmaz.
- Korunacak akışlar: araç seçenekleri, konumlar, araç varsayılanları, ilan metni ayrıştırma ve analiz; seçilen kaynakta bulunan diğer B2C uçları da envantere dahil edilir.
- Ortak /api/arabam-vehicles yerine gerekirse B2C'ye özel korunan araç seçenekleri ucu açılır.
- Giriş/kayıt/doğrulama/sıfırlama için gereken sınırlı açık uçlar açıkça listelenir.
- B2B ve eski kopyalardaki alternatif yollarla B2C korumasının aşılamadığı doğrulanır.
- Yeni servis hazır olduğunda eski backend'deki açık /api/b2c/* yolları kaldırılır veya kapatılır. Bu değişiklik yeni B2C yayınıyla aynı dağıtımda yapılır; B2B hesapları ve JWT giriş davranışı korunur. Geri alma işlemi eski açık B2C yollarını yeniden erişime açmaz.
- Kullanıcıya özel kayıt eklenirse sahiplik backend sorgusunda uygulanır.
- Analiz ve metin ayrıştırmada güvenlik amaçlı istek sınırı premium kota olarak sunulmaz.

Dosya alanları: backend/search/views.py, search/urls.py ve B2C permission modülü.

## 7. Gelecekteki özellik yetkileri için küçük bağlantı noktası

- Sunucuda tek bir özellik yetkisi hesaplama fonksiyonu; frontend bilgiyi /api/b2c/me üzerinden alır.
- İlk sürümde mevcut B2C özellikleri tüm doğrulanmış kullanıcılara verilir; tanımsız yetki reddedilir.
- Kullanıcı frontend'den plan veya premium alanı göndererek yetki kazanamaz.
- Abonelik tablosu, sağlayıcı SDK'sı, ödeme simülasyonu, satın alma düğmesi ve fiyat planı bu aşamada eklenmez.

## 8. Doğrulama ve teslim

Backend testleri: kayıt, mükerrer e-posta/eşzamanlı kayıt, doğrulanmamış hesabın reddi, geçerli/süresi dolmuş/kullanılmış link, yeniden gönderme sınırı, CSRF reddi, çıkış ve parola sıfırlaması sonrası eski oturum, tüm B2C uçlarında girişsiz erişim reddi, B2C/B2B kimlik izolasyonu.

Veri ve geçiş kontrolleri: Ayrı hesap veritabanıyla mevcut referans verilerinden analiz üretilebilmesi; referans kaynağına yazma/migration yapılamaması; eski backend adresindeki B2C yollarının kapanması ve B2B JWT akışının çalışmaya devam etmesi.

Frontend testleri: giriş ekranı ve korunan yönlendirme, doğrulama bekleme, sayfa yenileme, oturum bitişi, mail/şifre hata durumları, çıkış. Mevcut analiz akışı için regresyon kontrolü.

Yayın benzeri HTTPS ortamında cookie/proxy/CSRF, doğrudan URL açılışı ve mail bağlantısı doğrulanır. Build ve ilgili testler geçer. README ile .env.example yeni akışı anlatır.

Tamamlanma ölçütü: Yeni kullanıcı kayıt olur, kendi mailini doğrular, giriş yapar ve mevcut B2C analizini kullanır. Girişsiz veya doğrulanmamış kullanıcı aynı veriye doğrudan API ile ulaşamaz. B2B erişimi ayrı kalır. Ödeme hesabı bu teslimin önkoşulu değildir.

## Ödeme aşaması

Sonraya bırakıldı; bu planda uygulanacak ödeme işi yok.

## Kaynaklar

- https://docs.allauth.org/en/latest/headless/index.html
- https://docs.allauth.org/en/latest/headless/integrations.html
- https://docs.allauth.org/en/dev/account/configuration.html
- https://www.django-rest-framework.org/api-guide/authentication/
