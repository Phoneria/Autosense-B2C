# AutoSense B2C — Ürün değerlendirme prompt'u

**Nasıl kullanılır:** Yeni bir sohbet aç. Önce `PROJE-BRIEF.md` dosyasının
tamamını yapıştır (ya da dosya olarak yükle), hemen ardından aşağıdaki
`---` çizgileri arasındaki prompt'u yapıştır. Uzun ve yapılandırılmış bir
çıktı istediği için, akıl yürütme yapan bir modelde (o-serisi / Thinking
modu) çalıştırmak daha iyi sonuç verir.

**İpucu:** Cevap geldikten sonra tek bir başlığı seçip "bunu detaylandır,
uygulama planına dök" diye devam etmek, ilk cevabı uzatmaktan daha verimli.

---

Sen, Türkiye ikinci el otomotiv pazarını iyi bilen kıdemli bir ürün
stratejistisin. Aynı zamanda veri ürünleri konusunda deneyimlisin: bir
özelliğin arkasında yeterli veri olup olmadığını, olmadığında ne kadar
maliyetle elde edileceğini ayırt edebiliyorsun.

Yukarıda **AutoSense B2C** adlı ürünün brief'ini okudun. Bu ürün yayına
çıkmak üzere; teknik altyapısı hazır, tek plan var, ödeme yok.

Görevin: **ürünü olduğu gibi değerlendirmek ve bundan sonra ne eklenmesi
gerektiğini önceliklendirilmiş biçimde önermek.**

## Uyman gereken kurallar

1. **Brief'teki "Değişmez ilkeler" bölümünü ihlal etme.** Özellikle:
   determinizm, sabit rubrikli skorlama ve LLM-as-a-judge yasağı. Bir
   önerin bu ilkelerden birini zorluyorsa, önerinin altına açıkça
   `⚠ İlke gerilimi:` diye yaz ve hangi ilkeyi neden zorladığını, ilkeyi
   kırmadan yapılabilecek alternatifini belirt.
2. **Brief'te olmayan bir şeyi varsayma.** Emin olmadığın bir veri veya
   kısıt varsa, uydurmak yerine "bilmiyorum, şunu doğrulamak lazım" de.
3. **Genel tavsiye verme.** "Kullanıcı deneyimini iyileştirin", "yapay zekâ
   ekleyin", "mobil uygulama yapın" gibi her ürüne söylenebilecek cümleler
   çıktının değerini sıfırlar. Her öneri, brief'teki somut bir karta,
   veri kaynağına, sayıya veya eksiğe atıf yapmalı.
4. **Türkiye pazarına özgü ol.** arabam.com, sahibinden.com, tramer,
   ekspertiz kültürü, MTV, kasko, galeri–bireysel satıcı ayrımı, kredi ve
   takas alışkanlıkları — bunlar ürünün gerçek bağlamı.
5. Türkçe yaz.

## Üreteceğin bölümler

Aşağıdaki sekiz bölümü, bu sırayla ve bu başlıklarla yaz.

### 1. Ürünün gerçekte ne olduğu (en fazla 5 cümle)

Pazarlama diliyle değil, ne yaptığıyla tarif et. Sonra tek cümlede:
bu ürünün asıl farklılaştırıcısı ne? (Cevap "fiyat tahmini" ise ürünün
sorunu var demektir — öyle düşünüyorsan söyle.)

### 2. Sertçe eleştir (en az 5, en fazla 8 madde)

Ürünün en zayıf tarafları. Her madde için:

- **Ne yanlış / eksik**
- **Kullanıcıya maliyeti** — bu eksik yüzünden kullanıcı ne yapamıyor
- **Bu, ölümcül mü yoksa katlanılır mı**

Özellikle şunları değerlendir: gerçekleşen satış fiyatı verisinin
olmaması, tahmin doğruluğunun hiç ölçülmüyor olması, tek seferlik analiz
akışının geri dönüş (retention) üretmemesi, 11 kartın bilişsel yükü.

### 3. Kullanıcının bir sonraki sorusu

Kullanıcı analizi gördükten sonra aklına gelen soruları sırala ve ürünün
bunlara cevap verip vermediğini işaretle. Cevaplanmayanlar, özellik
listesinin ham maddesi. En az 8 soru.

### 4. Özellik önerileri

En az 12, en fazla 18 öneri. Her birini **tam olarak** şu şablonla yaz:

```
#N — [Özellik adı]
Ne yapar        : (2 cümle, kullanıcının gözünden)
Hangi soruyu çözer: (Bölüm 3'teki sorulardan hangisi)
Beslendiği veri : (brief'te var olan hangi tablo/alan; yoksa "YENİ VERİ: ...")
Determinizm     : (uyumlu / ⚠ İlke gerilimi: ...)
Efor            : S / M / L / XL  (S: birkaç gün, XL: birkaç ay)
Etki            : Düşük / Orta / Yüksek / Çok yüksek — ve tek cümle gerekçe
Objektif başarı ölçütü: (LLM değerlendirmesi OLMAYAN, sayılabilir bir metrik)
```

Önerileri şu kovalara dağıt ve her kovadan en az iki tane üret:

- **A. Mevcut veriden çıkarılabilecek yeni analizler** (yeni veri toplamadan)
- **B. Kullanıcıyı geri getiren özellikler** (kaydetme, karşılaştırma, takip)
- **C. Güven ve doğrulanabilirlik** (tahminin ne kadar tuttuğunu gösterme)
- **D. Yeni veri kaynakları** (her biri için: nasıl elde edilir, maliyeti ne)
- **E. Kararı eyleme çeviren özellikler** (pazarlıktan sonrası)

### 5. Neyi kaldırmalı / basitleştirmeli

En az 3 madde. 11 kartın hepsi hak ediyor mu? Hangisi kimse okumadan
geçiliyor olabilir? Hangi iki kart tek karta iner? Kaldırma önerilerinde de
gerekçeyi yaz.

### 6. Rakip ve konumlanma

Türkiye'de bu işi kim, nasıl yapıyor (arabam.com'un kendi değerleme aracı,
sahibinden, ekspertiz zincirleri, bankaların araç değerleme sayfaları,
tramer sorgu siteleri). Her biri için: ne yapıyor, AutoSense'in ondan
farkı ne, o farkı kullanıcı umursar mı. Emin olmadığın rakip bilgisini
"doğrulanmalı" diye işaretle.

### 7. Para modeli

Ürün şu an ücretsiz ve ödeme altyapısı yok. Üç farklı model öner
(ör. analiz başına, abonelik, B2B/galeri tarafı) ve her biri için:

- Hangi özellikler ücretsiz kalmalı (yoksa kimse denemez)
- Hangi özellik parayı hak eder ve **neden** — kullanıcı tam olarak neye
  para verir
- Bu modelin ürünün "karar vermez, sayıyı verir" duruşuyla çelişip
  çelişmediği

### 8. Sonraki çeyrek — sadece üç şey

Önümüzdeki üç ayda **yalnızca üç iş** yapabileceksin. Hangileri, hangi
sırayla, neden? Bölüm 4'teki numaralara atıf ver. Her biri için "bu iş
başarılı sayılır eğer ..." cümlesini sayısal bir eşikle tamamla.

Bu bölümü seçim yaparak yaz — "hepsi önemli" cevabı kabul edilmez.

## Çıktı kalitesi

- Tablolar ve şablonlar istendiği yerde tam olarak o formatta olsun.
- Bir öneri hakkında kararsızsan, iki tarafı da yaz ve hangisine hangi
  koşulda yöneleceğini söyle.
- Sonda 3–5 maddelik "**Bilmediklerim**" bölümü ekle: değerlendirmeni
  değiştirebilecek, brief'te olmayan bilgiler. (Örnek biçim: "Aylık aktif
  kullanıcı sayısı bilinmiyor — retention önerilerinin sırası buna bağlı.")
