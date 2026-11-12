import { Link } from "react-router-dom";
import Logo from "./Logo";
import { SELLER } from "../../seller";

export const CONTACT_EMAIL = "autoosense@gmail.com";

/** Uygulama ve herkese açık sayfalarda ortak footer. */
export default function SiteFooter() {
  return (
    <footer className="as-footer">
      <div className="as-footer-inner">
        <div className="as-footer-brand">
          <Logo />
          <p>
            Analizler yayındaki ilanların fiyatlarına dayanan tahminlerdir; ilan fiyatı satış fiyatı değildir.
            Sonuçlar ekspertiz raporu ve yerinde incelemenin yerini tutmaz.
          </p>
          <p className="as-footer-seller">
            {SELLER.name} · {SELLER.address}<br />
            Tel: <a href={SELLER.phoneHref}>{SELLER.phone}</a> · {SELLER.taxOffice} · VKN {SELLER.taxNo}
          </p>
        </div>
        <nav className="as-footer-links" aria-label="Alt bağlantılar">
          <Link to="/hakkimizda">Hakkımızda</Link>
          <Link to="/fiyatlar">Fiyatlar</Link>
          <Link to="/iletisim">İletişim</Link>
          <Link to="/mesafeli-satis-sozlesmesi">Mesafeli satış sözleşmesi</Link>
          <Link to="/on-bilgilendirme">Ön bilgilendirme formu</Link>
          <Link to="/iptal-iade">Teslimat ve iade</Link>
          <Link to="/gizlilik">Gizlilik ve çerezler</Link>
          <Link to="/kvkk">KVKK aydınlatma metni</Link>
          <a href={`mailto:${CONTACT_EMAIL}?subject=AutoSense%20ileti%C5%9Fim`}>{CONTACT_EMAIL}</a>
          <a href={SELLER.instagram} target="_blank" rel="noopener noreferrer">Instagram</a>
        </nav>
      </div>
      <div className="as-footer-bottom">
        <span>© {new Date().getFullYear()} AutoSense</span>
        <img className="as-pay-logos" src="/odeme/iyzico-logo-band.svg" width="429" height="32" alt="Güvenli ödeme: iyzico ile Öde, Mastercard, Visa, American Express, Troy" loading="lazy" />
      </div>
    </footer>
  );
}
