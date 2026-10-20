import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams, useLocation } from "react-router-dom";
import { authRequest, resend } from "../auth/api";
import { ApiError } from "../http";
import { useAuth } from "../auth/AuthProvider";
import { safeNext } from "../sections";
import { GoogleButton, googleErrorMessage } from "../auth/google";
import Logo from "../components/shell/Logo";

function Shell({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <div className="as-auth">
      <header className="as-auth-top">
        <Logo />
        <Link to="/" className="as-link-quiet">Ana sayfa</Link>
      </header>
      <main className="as-auth-main">
        <div className="auth-card as-auth-card">
          <h1 className="as-auth-title">{title}</h1>
          <p className="auth-intro">{intro}</p>
          {children}
        </div>
        <p className="as-auth-note">Tahminler ilan fiyatlarına dayanır; ekspertiz yerine geçmez.</p>
      </main>
      <footer className="as-auth-foot">
        <span>© {new Date().getFullYear()} AutoSense</span>
        <nav className="auth-legal" aria-label="Yasal bağlantılar"><Link to="/gizlilik">Gizlilik ve çerezler</Link><Link to="/kvkk">KVKK aydınlatma metni</Link></nav>
      </footer>
    </div>
  );
}
function Input({ label, type, value, onChange, autoComplete }: { label: string; type: string; value: string; onChange: (value: string) => void; autoComplete: string }) {
  const [show, setShow] = useState(false);
  const isPassword = type === "password";
  const input = <input type={isPassword && show ? "text" : type} value={value} onChange={e => onChange(e.target.value)} autoComplete={autoComplete} required maxLength={type === "email" ? 254 : 128} />;
  return <label className="field"><span>{label}</span>{isPassword ? <div className="password-wrap">{input}<button type="button" className="password-toggle" aria-pressed={show} aria-label={show ? "Parolayı gizle" : "Parolayı göster"} onClick={() => setShow(v => !v)}>{show ? "Gizle" : "Göster"}</button></div> : input}</label>;
}
function ErrorMessage({ message }: { message: string }) { return message ? <p className="auth-error" role="alert">{message}</p> : null; }
const PENDING_EMAIL = "b2c:verification-email";
function rememberEmail(email: string) {
  try { sessionStorage.setItem(PENDING_EMAIL, email.trim()); } catch { /* Route state still works when storage is unavailable. */ }
}
function pendingEmail() {
  try { return sessionStorage.getItem(PENDING_EMAIL) || ""; } catch { return ""; }
}
export function LoginPage() {
  const { user, loading, reload } = useAuth(); const navigate = useNavigate(); const [params] = useSearchParams();
  const [email, setEmail] = useState(""), [password, setPassword] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState(() => googleErrorMessage(params.get("error")));
  if (!loading && user) return <Navigate to={safeNext(params.get("next"))} replace />;
  async function submit(e: FormEvent) { e.preventDefault(); setBusy(true); setError(""); try {
    const data = await authRequest("auth/login", { email: email.trim(), password });
    if (data.data?.flows?.some(f => f.id === "verify_email" && f.is_pending)) { rememberEmail(email); navigate("/verify-email", { state: { email: email.trim() } }); return; }
    if (!await reload()) throw new Error("Giriş tamamlanamadı. E-posta adresinizi ve parolanızı kontrol edin.");
    navigate(safeNext(params.get("next")), { replace: true });
  } catch (e) { setError(e instanceof Error ? e.message : "Giriş yapılamadı."); } finally { setBusy(false); } }
  return <Shell title="Tekrar hoş geldiniz." intro="Araç analizinize devam etmek için giriş yapın."><GoogleButton /><form onSubmit={submit} className="auth-form"><Input label="E-posta" type="email" autoComplete="username" value={email} onChange={setEmail} /><Input label="Parola" type="password" autoComplete="current-password" value={password} onChange={setPassword} /><Link className="auth-forgot" to="/forgot-password">Parolamı unuttum</Link><ErrorMessage message={error} /><button className="primary-button" disabled={busy || loading}>{busy ? "Giriş yapılıyor…" : "Giriş yap"}<span>→</span></button></form><p className="auth-switch">Hesabınız yok mu? <Link to="/signup">Hesap oluşturun</Link></p></Shell>;
}
export function SignupPage() {
  const navigate = useNavigate(); const [email, setEmail] = useState(""), [password, setPassword] = useState(""), [confirm, setConfirm] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function submit(e: FormEvent) { e.preventDefault(); if (password !== confirm) { setError("Parolalar eşleşmiyor."); return; } setBusy(true); setError(""); try { await authRequest("auth/signup", { email: email.trim(), password }); rememberEmail(email); navigate("/verify-email", { state: { email: email.trim() } }); } catch (e) { if (e instanceof ApiError && e.status === 409) { rememberEmail(email); navigate("/verify-email", { state: { email: email.trim() } }); return; } setError(e instanceof Error ? e.message : "Hesap oluşturulamadı."); } finally { setBusy(false); } }
  return <Shell title="İlk adım, hesabınız." intro="Hesabınızı oluşturun, e-postanızı doğrulayın ve araçları analiz etmeye başlayın."><GoogleButton label="Google ile kayıt ol" /><form className="auth-form" onSubmit={submit}><Input label="E-posta" type="email" autoComplete="username" value={email} onChange={setEmail} /><Input label="Parola" type="password" autoComplete="new-password" value={password} onChange={setPassword} /><p className="auth-hint">En az 10 karakter kullanın. Yaygın veya yalnızca rakamlardan oluşan parolalardan kaçının.</p><Input label="Parola tekrar" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} /><ErrorMessage message={error} /><button className="primary-button" disabled={busy}>{busy ? "Hesap oluşturuluyor…" : "Hesap oluştur"}<span>→</span></button></form><p className="auth-switch">Zaten hesabınız var mı? <Link to="/login">Giriş yapın</Link></p></Shell>;
}
export function VerifyEmailPage() {
  const location = useLocation(); const navigate = useNavigate(); const { reload } = useAuth();
  const [email, setEmail] = useState(() => location.state?.email || pendingEmail()), [code, setCode] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState(""), [success, setSuccess] = useState(false), [notice, setNotice] = useState("");
  // The code belongs to this browser session, so a lost session reads as 409.
  // Entering it also completes the pending login: allauth treats the code as
  // proof of identity because only the session that signed up can supply it.
  async function verify(e: FormEvent) { e.preventDefault(); setBusy(true); setError(""); setNotice(""); try {
    await authRequest("auth/email/verify", { key: code.trim() });
    try { sessionStorage.removeItem(PENDING_EMAIL); } catch { /* Optional UI state. */ }
    if (await reload()) { navigate("/", { replace: true }); return; }
    setSuccess(true);
  } catch (e) { setError(e instanceof ApiError && e.status === 409 ? "Bu tarayıcıda bekleyen bir doğrulama isteği yok. Aşağıdan yeni bir kod isteyin." : e instanceof Error ? e.message : "Kod doğrulanamadı."); } finally { setBusy(false); } }
  async function send(e: FormEvent) { e.preventDefault(); setBusy(true); setError(""); setNotice(""); try { await resend(email.trim()); setCode(""); setNotice("Doğrulama gerekiyorsa kod gönderildi. Gelen kutunuzu ve spam klasörünüzü kontrol edin."); } catch (e) { setError(e instanceof Error ? e.message : "E-posta gönderilemedi."); } finally { setBusy(false); } }
  return <Shell title={success ? "E-postanız doğrulandı." : "E-postanızı doğrulayın."} intro={success ? "Hesabınız hazır. Parolanızla giriş yaparak analize başlayabilirsiniz." : "Size gönderdiğimiz 6 haneli kodu aşağıya girin. Spam klasörünü de kontrol etmeyi unutmayın."}>{success ? <Link className="primary-button" to="/login">Giriş yap</Link> : <><form className="auth-form" onSubmit={verify}><label className="field"><span>Doğrulama kodu</span><input type="text" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value)} required maxLength={12} /></label>{(location.state?.email || pendingEmail()) && <p className="auth-hint">Kod <strong>{email}</strong> adresine gönderildi.</p>}<ErrorMessage message={error} /><button className="primary-button" disabled={busy}>{busy ? "Doğrulanıyor…" : "E-postamı doğrula"}<span>→</span></button></form><form className="auth-form resend-form" onSubmit={send}><>{(location.state?.email || pendingEmail()) ? <p className="auth-hint">Kod gelmediyse aşağıdan yeniden gönderebilirsiniz.</p> : <Input label="E-posta" type="email" autoComplete="email" value={email} onChange={setEmail} />}</><button className="secondary-button" disabled={busy}>{busy ? "İşleniyor…" : "Yeni kod gönder"}</button></form>{notice && <p className="auth-success" role="status">{notice}</p>}<p className="auth-switch"><Link to="/login">Girişe dön</Link></p></>}</Shell>;
}
export function ForgotPasswordPage() {
  const [email, setEmail] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState(""), [sent, setSent] = useState(false);
  async function submit(e: FormEvent) { e.preventDefault(); setBusy(true); setError(""); try { await authRequest("auth/password/request", { email: email.trim() }); setSent(true); } catch (e) { setError(e instanceof Error ? e.message : "İşlem tamamlanamadı."); } finally { setBusy(false); } }
  return <Shell title="Parolanızı yenileyin." intro="E-posta adresinizi girin; parola sıfırlama bağlantısını gönderelim."><form className="auth-form" onSubmit={submit}><Input label="E-posta" type="email" autoComplete="email" value={email} onChange={setEmail} /><ErrorMessage message={error} />{sent && <p className="auth-success" role="status">Bu adresle bir hesap varsa sıfırlama bağlantısı gönderildi. Gelen kutunuzu ve spam klasörünüzü kontrol edin.</p>}<button className="primary-button" disabled={busy}>{busy ? "Gönderiliyor…" : "Sıfırlama bağlantısı gönder"}</button></form><p className="auth-switch"><Link to="/login">Girişe dön</Link></p></Shell>;
}
export function ResetPasswordPage() {
  const { key } = useParams(); const { reload } = useAuth(); const [password, setPassword] = useState(""), [confirm, setConfirm] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState(""), [success, setSuccess] = useState(false);
  useEffect(() => { setSuccess(false); setError(""); setPassword(""); setConfirm(""); }, [key]);
  async function submit(e: FormEvent) { e.preventDefault(); if (password !== confirm) { setError("Parolalar eşleşmiyor."); return; } setBusy(true); setError(""); try { await authRequest("auth/password/reset", { key: key!, password }); await reload(); setSuccess(true); } catch (e) { setError(e instanceof Error ? e.message : "Bağlantı geçersiz veya süresi dolmuş olabilir."); } finally { setBusy(false); } }
  return <Shell title={success ? "Parolanız yenilendi." : "Yeni parolanızı belirleyin."} intro={success ? "Yeni parolanızla giriş yapabilirsiniz." : "Hesabınız için güçlü ve benzersiz bir parola seçin."}>{success ? <Link className="primary-button" to="/login">Giriş yap</Link> : key ? <form className="auth-form" onSubmit={submit}><Input label="Yeni parola" type="password" autoComplete="new-password" value={password} onChange={setPassword} /><Input label="Yeni parola tekrar" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} /><ErrorMessage message={error} /><button className="primary-button" disabled={busy}>{busy ? "Kaydediliyor…" : "Parolayı kaydet"}</button></form> : <p className="auth-error" role="alert">Sıfırlama bağlantısı eksik. E-postanızdaki bağlantıyı açın.</p>}{!success && <p className="auth-switch"><Link to="/forgot-password">Yeni sıfırlama bağlantısı iste</Link></p>}</Shell>;
}
