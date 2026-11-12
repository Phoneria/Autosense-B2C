import { Link } from "react-router-dom";
import { CONTACT_EMAIL, LegalPage } from "./PublicPages";
import { SELLER } from "../seller";
import { PUBLIC_PLANS, VAT_NOTE } from "../billingDisplay";
import { cleanFeatures } from "../components/PlanCards";

const SALES_UPDATED = "13 Kasım 2026";

function SellerBlock() {
  return (
    <ul>
      <li><strong>Satıcı / hizmet sağlayıcı:</strong> {SELLER.name} ({SELLER.brand})</li>
      <li><strong>Adres:</strong> {SELLER.address}</li>
      <li><strong>Telefon:</strong> <a href={SELLER.phoneHref}>{SELLER.phone}</a></li>
      <li><strong>E-posta:</strong> <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></li>
      <li><strong>Vergi dairesi / Vergi kimlik no:</strong> {SELLER.taxOffice} / {SELLER.taxNo}</li>
      <li><strong>Web sitesi:</strong> {SELLER.web}</li>
    </ul>
  );
}

function PlanTable() {
  return (
    <ul>
      {PUBLIC_PLANS.map((p) => (
        <li key={p.id}><strong>{p.name}</strong>: {p.price_label}. {cleanFeatures(p.features, p.id === "premium").join(", ")}.</li>
      ))}
    </ul>
  );
}

const DELIVERY = "Hizmet dijitaldir; fiziksel teslimat yapılmaz. Ödeme onaylandığında seçilen plan, Alıcı'nın AutoSense hesabına elektronik ortamda anında tanımlanır.";
const RENEWAL = "Ücretli planlar aylık aboneliktir. Alıcı iptal etmediği sürece abonelik her ay aynı ödeme aracından yenilenir. İptal, içinde bulunulan dönemin sonunda geçerli olur; dönem sonuna kadar plan kullanılmaya devam eder.";
const WITHDRAWAL_EXCEPTION = "Mesafeli Sözleşmeler Yönetmeliği'nin 15. maddesinin birinci fıkrasının (ğ) bendi uyarınca, elektronik ortamda anında ifa edilen hizmetlere ilişkin sözleşmelerde cayma hakkı kullanılamaz. Alıcı, sipariş sırasında hizmetin hemen başlamasını ve bu nedenle cayma hakkının sona ereceğini ayrıca onaylar.";

export function PreInfoPage() {
  return (
    <LegalPage updated={SALES_UPDATED} title="Ön Bilgilendirme Formu">
      <p>Bu form, 6502 sayılı Tüketicinin Korunması Hakkında Kanun ve Mesafeli Sözleşmeler Yönetmeliği uyarınca, sipariş verilmeden önce Alıcı'yı bilgilendirmek amacıyla hazırlanmıştır.</p>
      <h2>1. Satıcı bilgileri</h2>
      <SellerBlock />
      <h2>2. Hizmetin temel nitelikleri ve fiyatı</h2>
      <p>AutoSense, ikinci el araç ilanları için piyasa değeri tahmini, pazarlık ve bölgesel fiyat karşılaştırması sunan çevrim içi bir hizmettir. Planlar ve aylık fiyatları:</p>
      <PlanTable />
      <p>{VAT_NOTE} Fiyatlara ek olarak kargo, teslimat veya başka bir ücret alınmaz.</p>
      <h2>3. Ödeme</h2>
      <p>Ödeme, kredi kartı veya banka kartı ile güvenli ödeme sayfası üzerinden peşin alınır. Kart bilgileri Satıcı tarafından saklanmaz.</p>
      <h2>4. İfa ve teslimat</h2>
      <p>{DELIVERY}</p>
      <h2>5. Sözleşme süresi ve iptal</h2>
      <p>{RENEWAL} Ayrıntılar için <Link to="/iptal-iade">İptal ve İade Koşulları</Link>'na bakınız.</p>
      <h2>6. Cayma hakkı</h2>
      <p>{WITHDRAWAL_EXCEPTION}</p>
      <h2>7. Şikayet ve itirazlar</h2>
      <p>Şikayetlerinizi yukarıdaki adres, telefon veya e-posta üzerinden iletebilirsiniz. Uyuşmazlıklarda, Ticaret Bakanlığı'nca her yıl belirlenen parasal sınırlar dahilinde Alıcı'nın veya Satıcı'nın yerleşim yerindeki Tüketici Hakem Heyetleri, bu sınırları aşan durumlarda Tüketici Mahkemeleri yetkilidir.</p>
    </LegalPage>
  );
}

export function DistanceSalesPage() {
  return (
    <LegalPage updated={SALES_UPDATED} title="Mesafeli Satış Sözleşmesi">
      <h2>1. Taraflar</h2>
      <p><strong>Satıcı:</strong></p>
      <SellerBlock />
      <p><strong>Alıcı:</strong> auto-sense.com.tr üzerinde hesap oluşturarak ücretli bir plan satın alan, hesabında kayıtlı e-posta adresiyle tanımlanan kişi.</p>
      <h2>2. Konu</h2>
      <p>Bu sözleşme, Alıcı'nın auto-sense.com.tr üzerinden elektronik ortamda satın aldığı AutoSense planına ilişkin olarak, 6502 sayılı Tüketicinin Korunması Hakkında Kanun ve Mesafeli Sözleşmeler Yönetmeliği hükümleri uyarınca tarafların hak ve yükümlülüklerini düzenler.</p>
      <h2>3. Hizmet ve bedel</h2>
      <PlanTable />
      <p>{VAT_NOTE} Satın alınan plan, plan adı ve bedel sipariş özetinde ayrıca gösterilir.</p>
      <h2>4. Ödeme</h2>
      <p>Bedel, kredi kartı veya banka kartı ile peşin ödenir. {RENEWAL}</p>
      <h2>5. İfa</h2>
      <p>{DELIVERY}</p>
      <h2>6. Cayma hakkı</h2>
      <p>{WITHDRAWAL_EXCEPTION}</p>
      <h2>7. İptal ve iade</h2>
      <p>Alıcı aboneliğini istediği zaman iptal edebilir; içinde bulunulan dönem için ödenen bedel iade edilmez. Mükerrer tahsilat veya Satıcı kaynaklı nedenle hizmetin hiç sunulamaması gibi durumlarda iade yapılır. Ayrıntılar: <Link to="/iptal-iade">İptal ve İade Koşulları</Link>.</p>
      <h2>8. Tarafların yükümlülükleri</h2>
      <ul>
        <li>Satıcı, satın alınan planın özelliklerini plan süresi boyunca sunmakla yükümlüdür. Planlı bakım ve zorunlu teknik kesintiler mümkün olduğunca kısa tutulur.</li>
        <li>AutoSense sonuçları yayındaki ilan fiyatlarına dayanan tahminlerdir; ilan fiyatı satış fiyatı değildir ve sonuçlar ekspertiz raporu veya yerinde incelemenin yerini tutmaz. Alıcı, satın alma kararlarını kendi değerlendirmesiyle verir.</li>
        <li>Alıcı, hesabını üçüncü kişilerle paylaşmamak ve hizmeti otomatik araçlarla aşırı yük oluşturacak şekilde kullanmamakla yükümlüdür.</li>
      </ul>
      <h2>9. Kişisel veriler</h2>
      <p>Kişisel veriler <Link to="/kvkk">KVKK Aydınlatma Metni</Link> ve <Link to="/gizlilik">Gizlilik ve Çerez Politikası</Link> kapsamında işlenir.</p>
      <h2>10. Uyuşmazlıklar</h2>
      <p>Ticaret Bakanlığı'nca her yıl belirlenen parasal sınırlar dahilinde Tüketici Hakem Heyetleri, bu sınırları aşan durumlarda Tüketici Mahkemeleri yetkilidir.</p>
      <h2>11. Yürürlük</h2>
      <p>Alıcı, siparişi onaylamadan önce <Link to="/on-bilgilendirme">Ön Bilgilendirme Formu</Link>'nu ve bu sözleşmeyi okuyup elektronik ortamda onaylar. Sözleşme, ödemenin onaylanmasıyla yürürlüğe girer.</p>
    </LegalPage>
  );
}

export function CancelRefundPage() {
  return (
    <LegalPage updated={SALES_UPDATED} title="İptal ve İade Koşulları">
      <h2>Aboneliği iptal etme</h2>
      <ul>
        <li>Ücretli planınızı istediğiniz zaman iptal edebilirsiniz. İptal için <a href={`mailto:${CONTACT_EMAIL}?subject=AutoSense%20abonelik%20iptali`}>{CONTACT_EMAIL}</a> adresine hesabınızdaki e-posta adresinden yazmanız yeterlidir.</li>
        <li>İptal, içinde bulunulan aylık dönemin sonunda geçerli olur. Dönem sonuna kadar planınızı kullanmaya devam edersiniz; sonraki ay için ücret alınmaz.</li>
        <li>Dönem sonunda hesabınız ücretsiz Basic plana geçer; hesabınız ve geçmişiniz silinmez.</li>
      </ul>
      <h2>İade</h2>
      <ul>
        <li>Plan ödeme anında hesabınıza tanımlandığı için <strong>içinde bulunulan ay için ödenen bedel iade edilmez</strong> (Mesafeli Sözleşmeler Yönetmeliği m. 15/1-ğ).</li>
        <li>Şu durumlarda ödediğiniz tutar iade edilir: aynı dönem için birden fazla tahsilat yapılması, teknik bir hata nedeniyle planın hesabınıza hiç tanımlanmaması veya Satıcı kaynaklı nedenle hizmetin sunulamaması.</li>
        <li>İadeler, talebin onaylanmasından itibaren 14 gün içinde ödemenin yapıldığı karta yapılır. Tutarın hesabınıza yansıma süresi bankanıza bağlıdır.</li>
      </ul>
      <h2>Basic plan</h2>
      <p>Basic plan ücretsizdir; iptal veya iade işlemi gerektirmez.</p>
      <h2>İletişim</h2>
      <p>{SELLER.name} · {SELLER.address} · Tel: <a href={SELLER.phoneHref}>{SELLER.phone}</a> · <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
    </LegalPage>
  );
}
