import { Link } from "react-router-dom";

/** Koyu zemin için tek logo kullanımı (header, footer, giriş ekranı). */
export default function Logo({ to = "/", label = "AutoSense ana sayfa" }: { to?: string; label?: string }) {
  return (
    <Link to={to} className="as-logo" aria-label={label}>
      <img src="/autosense-logo-trim.png" alt="AutoSense" width={143} height={21} />
    </Link>
  );
}
