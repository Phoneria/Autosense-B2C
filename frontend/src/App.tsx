import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import AnalysisPage from "./pages/AnalysisPage";
import { LoginPage, SignupPage, VerifyEmailPage, ForgotPasswordPage, ResetPasswordPage } from "./pages/AuthPages";
import { CookieNotice, KvkkPage, LandingPage, PricingPage, PrivacyPage } from "./pages/PublicPages";
import { useAuth } from "./auth/AuthProvider";
import { SECTION_PATHS } from "./sections";
function TokenPage({ reset = false }: { reset?: boolean }) {
  const { key } = useParams();
  return reset ? <ResetPasswordPage key={key || "missing"} /> : <VerifyEmailPage key={key || "missing"} />;
}
// Giriş yapmamış ziyaretçi ana sayfada tanıtımı görür; giriş yapan analiz ekranını.
// Bölüm adresleri (/rehber, /bolgesel…) tek bir yerleşim rotasının altında: bölüm
// değişince AnalysisPage yeniden kurulmaz, girilen form verileri korunur.
function Home() {
  const { user, loading } = useAuth();
  const { pathname, search } = useLocation();
  if (loading) return <main className="auth-loading" role="status">Oturumunuz kontrol ediliyor…</main>;
  if (user) return <AnalysisPage />;
  if (pathname === "/") return <LandingPage />;
  return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />;
}
// Fiyat sayfası herkese açık; giriş yapmış kullanıcı planlarını Hesabım'da görür.
function Pricing() {
  const { user, loading } = useAuth();
  if (loading) return <main className="auth-loading" role="status">Oturumunuz kontrol ediliyor…</main>;
  return user ? <Navigate to="/hesabim#planlar" replace /> : <PricingPage />;
}
export default function App() { return <BrowserRouter><AuthProvider><CookieNotice /><Routes>
  <Route path="/login" element={<LoginPage />} /><Route path="/signup" element={<SignupPage />} />
  <Route path="/verify-email" element={<TokenPage />} /><Route path="/verify-email/:key" element={<TokenPage />} />
  <Route path="/forgot-password" element={<ForgotPasswordPage />} /><Route path="/reset-password/:key" element={<TokenPage reset />} />
  <Route path="/reset-password" element={<TokenPage reset />} />
  <Route path="/fiyatlar" element={<Pricing />} />
  <Route path="/gizlilik" element={<PrivacyPage />} /><Route path="/kvkk" element={<KvkkPage />} />
  <Route element={<Home />}>
    {Object.values(SECTION_PATHS).map(path => <Route key={path} path={path} />)}
  </Route>
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes></AuthProvider></BrowserRouter>; }
