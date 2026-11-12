import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import Logo from "./Logo";
import AccountBadge from "../AccountBadge";
import AccountMenu from "../AccountMenu";
import { SECTION_PATHS } from "../../sections";

const NAV = [
  { to: SECTION_PATHS.analysis, label: "Analiz", feature: "" },
  { to: SECTION_PATHS.guide, label: "Araç Rehberi", feature: "guide" },
  { to: SECTION_PATHS.regional, label: "Bölgesel Fırsatlar", feature: "regional" },
] as const;
/** Fiyatlar: Hesabım sayfasındaki plan kartlarına gider. */
const PRICING_TO = `${SECTION_PATHS.profile}#planlar`;

/** Giriş yapmış kullanıcının üst menüsü. Mobilde menü düğmesiyle açılır. */
export default function AppHeader({ can, onProfile }: { can: (feature: string) => boolean; onProfile: () => void }) {
  const { pathname, hash } = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); }, [pathname]);
  const toggle = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); toggle.current?.focus(); } };
    // Menü açıkken arka plan kaymaz; masaüstü genişliğine geçilirse menü kapanır.
    const wide = window.matchMedia("(min-width: 1024px)");
    const onWide = () => { if (wide.matches) setOpen(false); };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", esc);
    wide.addEventListener("change", onWide);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener("keydown", esc);
      wide.removeEventListener("change", onWide);
    };
  }, [open]);

  return (
    <header className={`as-header${open ? " is-open" : ""}`}>
      <div className="as-header-inner">
        <Logo label="Analiz sayfasına git" />
        <button type="button" ref={toggle} className="as-menu-toggle" aria-expanded={open} aria-controls="as-header-panel"
          onClick={() => setOpen(v => !v)}>
          <span className="as-menu-icon" aria-hidden="true" />
          <span>{open ? "Kapat" : "Menü"}</span>
        </button>
        <button type="button" className="as-menu-scrim" tabIndex={-1} aria-hidden="true" onClick={() => setOpen(false)} />
        <div className="as-header-panel" id="as-header-panel">
          <nav className="as-nav" aria-label="Bölümler">
            {NAV.map(item => {
              const locked = !!item.feature && !can(item.feature);
              return (
                <NavLink key={item.to} to={item.to} end
                  className={({ isActive }) => (isActive ? "active" : "")}>
                  {item.label}
                  {locked && <em className="as-lock">PRO</em>}
                </NavLink>
              );
            })}
            <NavLink to={PRICING_TO} className={() => (pathname === SECTION_PATHS.profile && hash === "#planlar" ? "active" : "")}>Fiyatlar</NavLink>
          </nav>
          <div className="as-account">
            <AccountBadge onOpen={onProfile} />
            <AccountMenu onProfile={onProfile} />
          </div>
        </div>
      </div>
    </header>
  );
}
