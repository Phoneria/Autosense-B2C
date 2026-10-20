import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthProvider";

export default function AccountMenu({ onProfile }: { onProfile: () => void }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  return (
    <div className="as-account-menu" ref={box}
      onKeyDown={e => { if (e.key === "Escape" && open) { e.stopPropagation(); setOpen(false); trigger.current?.focus(); } }}>
      <button type="button" ref={trigger} className="as-account-trigger" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen(!open)}>
        Hesabım <span className="as-caret" aria-hidden="true" />
      </button>
      {open && (
        <div className="as-account-dropdown" role="menu">
          {user?.email && <p className="as-account-email">{user.email}</p>}
          <button type="button" role="menuitem" onClick={() => { setOpen(false); onProfile(); }}>
            Hesabım ve plan
          </button>
          <button type="button" role="menuitem" className="danger" disabled={busy}
            onClick={() => { setError(""); setBusy(true); void logout().catch((e: Error) => setError(e.message)).finally(() => setBusy(false)); }}>
            {busy ? "Çıkış yapılıyor…" : "Çıkış yap"}
          </button>
          {error && <p role="alert" className="form-error">{error}</p>}
        </div>
      )}
    </div>
  );
}
