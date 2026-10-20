import { useEffect, useState } from "react";
import { refreshCsrf } from "../http";

const BASE = "/_allauth/browser/v1";
let googleEnabled: Promise<boolean> | null = null;

function isGoogleEnabled(): Promise<boolean> {
  if (!googleEnabled) googleEnabled = fetch(`${BASE}/config`, { credentials: "same-origin" })
    .then(r => r.ok ? r.json() : null)
    .then(d => Boolean(d?.data?.socialaccount?.providers?.some((p: { id: string }) => p.id === "google")))
    .catch(() => false);
  return googleEnabled;
}

export const GOOGLE_ERRORS: Record<string, string> = {
  cancelled: "Google ile giriş iptal edildi.",
  denied: "Google ile giriş iptal edildi.",
  unknown: "Google ile giriş yapılamadı. Lütfen tekrar deneyin.",
};

export function googleErrorMessage(code: string | null): string {
  if (!code) return "";
  return GOOGLE_ERRORS[code] || GOOGLE_ERRORS.unknown;
}

export function GoogleButton({ label = "Google ile devam et", divider = true, className = "" }: { label?: string; divider?: boolean; className?: string }) {
  const [enabled, setEnabled] = useState(false), [busy, setBusy] = useState(false);
  useEffect(() => { let alive = true; isGoogleEnabled().then(v => { if (alive) setEnabled(v); }); return () => { alive = false; }; }, []);
  if (!enabled) return null;
  async function start() {
    setBusy(true);
    try {
      const token = await refreshCsrf();
      const form = document.createElement("form");
      form.method = "POST";
      form.action = `${BASE}/auth/provider/redirect`;
      const fields: Record<string, string> = { provider: "google", process: "login", callback_url: "/login", csrfmiddlewaretoken: token };
      for (const [name, value] of Object.entries(fields)) {
        const input = document.createElement("input");
        input.type = "hidden"; input.name = name; input.value = value;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
    } catch { setBusy(false); }
  }
  return <>
    <button type="button" className={`google-button ${className}`.trim()} onClick={start} disabled={busy}>
      <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.7-6.7C35.6 2.4 30.2 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.8 6C12.4 13.6 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z"/><path fill="#FBBC05" d="M10.5 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.8-6C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.8-6z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.8 6C6.6 42.6 14.6 48 24 48z"/></svg>
      {busy ? "Google'a yönlendiriliyor…" : label}
    </button>
    {divider && <div className="auth-divider"><span>veya e-posta ile</span></div>}
  </>;
}
