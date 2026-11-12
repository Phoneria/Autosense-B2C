import { Link } from "react-router-dom";
import Logo from "./Logo";

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
        </div>
        <nav className="as-footer-links" aria-label="Alt bağlantılar">
          <Link to="/fiyatlar">Fiyatlar</Link>
          <Link to="/gizlilik">Gizlilik ve çerezler</Link>
          <Link to="/kvkk">KVKK aydınlatma metni</Link>
          <a href={`mailto:${CONTACT_EMAIL}?subject=AutoSense%20ileti%C5%9Fim`}>{CONTACT_EMAIL}</a>
        </nav>
      </div>
      <div className="as-footer-bottom">© {new Date().getFullYear()} AutoSense</div>
    </footer>
  );
}
