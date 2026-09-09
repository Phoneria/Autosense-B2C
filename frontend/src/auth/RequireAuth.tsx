import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";
export default function RequireAuth() {
  const { user, loading, error } = useAuth(); const location = useLocation();
  if (loading) return <main className="auth-loading" role="status">Oturumunuz kontrol ediliyor…</main>;
  if (error) return <main className="auth-loading"><p role="alert">{error}</p><button className="primary-button" onClick={() => window.location.reload()}>Tekrar dene</button></main>;
  return user ? <Outlet /> : <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
}
