import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import RequireAuth from "./auth/RequireAuth";
import AnalysisPage from "./pages/AnalysisPage";
import { LoginPage, SignupPage, VerifyEmailPage, ForgotPasswordPage, ResetPasswordPage } from "./pages/AuthPages";
function TokenPage({ reset = false }: { reset?: boolean }) {
  const { key } = useParams();
  return reset ? <ResetPasswordPage key={key || "missing"} /> : <VerifyEmailPage key={key || "missing"} />;
}
export default function App() { return <BrowserRouter><AuthProvider><Routes>
  <Route path="/login" element={<LoginPage />} /><Route path="/signup" element={<SignupPage />} />
  <Route path="/verify-email" element={<TokenPage />} /><Route path="/verify-email/:key" element={<TokenPage />} />
  <Route path="/forgot-password" element={<ForgotPasswordPage />} /><Route path="/reset-password/:key" element={<TokenPage reset />} />
  <Route path="/reset-password" element={<TokenPage reset />} />
  <Route element={<RequireAuth />}><Route path="/" element={<AnalysisPage />} /></Route>
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes></AuthProvider></BrowserRouter>; }
