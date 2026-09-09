# Eski B2C yayınının kapatılması

Bu bağımsız proje Autosense kaynak dosyalarını veya çalışan canlı sunucuyu değiştirmez.
Yeni servis yayına alınırken eski açık B2C uçları aynı geçişte kapatılmalıdır.

1. Canlı B2C domain/build kaynağını doğrulayın. Yeni arayüz, `/api/*` ve
   `/_allauth/*` trafiği bu projenin servisine gitmelidir.
2. Yeni serviste kayıt → gerçek gönderici e-postası → doğrulama → giriş → analiz
   akışını kontrol edin; girişsiz analiz isteği 401 olmalıdır.
3. Eski backend URL yapılandırmasından `/api/b2c/lookup-text`,
   `/api/b2c/locations`, `/api/b2c/vehicle-defaults`, `/api/b2c/analyze` yollarını
   kaldırın veya eski sunucuda 404/410 döndürün. Eski domain ve doğrudan origin
   adresinden erişimin kapalı olduğunu doğrulayın.
4. Eski B2B JWT girişini ve B2B iş akışlarını regresyon kontrolünden geçirin.
   B2B hesapları ve yetkilendirmesi bu projeye taşınmaz.
5. Eski `/api/arabam-vehicles` ortak kataloğunun B2B kullanımını ayrıca değerlendirin.
   Yeni B2C servisindeki katalog uçları korumalıdır; eski ortak katalog açık
   tutulursa katalog içeriğinin bütünüyle özel olduğu iddia edilmemelidir.
6. Geri alma gerekirse eski açık analiz yollarını yeniden açmayın. Geçici
   bakım yanıtı kullanın; kullanıcı ve oturum veritabanlarını koruyun.

Canlı sunucu erişimi/domain bilgileri olmadan bu geçiş yapılmış sayılmaz.
