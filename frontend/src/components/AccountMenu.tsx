import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthProvider";

export default function AccountMenu({ onProfile }: { onProfile: () => void }) {
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  return (
    <div className="account-menu" ref={box}>
      <button type="button" className="account-menu-trigger" aria-expanded={open} onClick={() => setOpen(!open)}>
        Hesabım <span aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div className="account-dropdown" role="menu">
          <button type="button" role="menuitem" onClick={() => { setOpen(false); onProfile(); }}>
            <strong>Profil</strong>
          </button>
          <button type="button" role="menuitem" className="danger"
            onClick={() => { setError(""); void logout().catch((e: Error) => setError(e.message)); }}><strong>Çıkış</strong>
          </button>
          {error && <p role="alert" className="form-error">{error}</p>}
        </div>
      )}
    </div>
  );
}
