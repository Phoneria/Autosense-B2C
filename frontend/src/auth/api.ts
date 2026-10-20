import { API, ApiError, request, refreshCsrf } from "../http";
import type { AuthResponse, User } from "./types";

// allauth answers with a stable error code; translate it into what the person
// should actually do. Server text is the fallback for codes not listed here.
const ERROR_MESSAGES: Record<string, string> = {
  email_taken: "Bu e-posta adresiyle kayıtlı bir hesap zaten var. Giriş yapın; parolanızı hatırlamıyorsanız “Parolamı unuttum” ile sıfırlayın.",
  duplicate_email: "Bu e-posta adresi zaten hesabınıza tanımlı.",
  unknown_email: "Bu e-posta adresine ait bir hesap bulunamadı.",
  email_password_mismatch: "E-posta adresi veya parola hatalı.",
  incorrect_password: "Parola hatalı.",
  account_inactive: "Bu hesap şu anda devre dışı.",
  unverified_primary_email: "Devam etmek için önce e-posta adresinizi doğrulamanız gerekiyor.",
  invalid_or_expired_key: "Bağlantı geçersiz veya süresi dolmuş. Yeni bir bağlantı isteyin.",
  invalid_password_reset: "Parola sıfırlama bağlantısı geçersiz. Yeni bir bağlantı isteyin.",
  incorrect_code: "Kod hatalı. E-postadaki 6 haneli kodu kontrol edip tekrar deneyin.",
  too_many_login_attempts: "Çok fazla başarısız giriş denemesi yapıldı. Bir süre sonra tekrar deneyin.",
  enter_current_password: "Mevcut parolanızı girin.",
  password_too_short: "Parola en az 10 karakter olmalı.",
  password_too_common: "Bu parola çok yaygın. Daha benzersiz bir parola seçin.",
  password_entirely_numeric: "Parola yalnızca rakamlardan oluşamaz.",
  password_too_similar: "Parola e-posta adresinize çok benziyor.",
};

const FIELD_LABELS: Record<string, string> = {
  email: "E-posta",
  password: "Parola",
  password1: "Parola",
  password2: "Parola tekrar",
  key: "Bağlantı",
};

// allauth returns field-level problems in errors[]; keep the field name so the
// person knows which input to fix.
function detailedMessage(errors?: AuthResponse["errors"]): string {
  if (!errors?.length) return "";
  return errors
    .map(e => {
      const known = ERROR_MESSAGES[e.code];
      if (known) return known;
      const label = e.param ? FIELD_LABELS[e.param] : "";
      return label ? `${label}: ${e.message}` : e.message;
    })
    .join(" ");
}

// Several allauth responses (409 conflict, CSRF rejection, server faults) carry
// no errors[] at all. Say what actually happened instead of one generic line.
function statusMessage(status: number): string {
  if (status === 400) return "Gönderilen bilgiler geçersiz. Alanları kontrol edip tekrar deneyin.";
  if (status === 403) return "Güvenlik doğrulaması geçersiz. Sayfayı yenileyip tekrar deneyin.";
  if (status === 404) return "İstek karşılanamadı. Bağlantı geçersiz veya süresi dolmuş olabilir.";
  if (status === 409) return "Bu tarayıcıda yarım kalmış bir kayıt veya giriş adımı var. Kaldığınız yerden devam edin.";
  if (status >= 500) return "Sunucuya şu anda ulaşılamıyor. Birazdan tekrar deneyin.";
  return "İşlem tamamlanamadı. Lütfen tekrar deneyin.";
}

// Kullanıcıya ham HTTP durum kodu gösterilmez; durum ApiError.status'ta kalır,
// geliştirme ortamında yalnızca konsola yazılır.
function annotate(message: string, status: number): string {
  if (import.meta.env.DEV) console.debug(`[auth] HTTP ${status}: ${message}`);
  return message;
}

export async function getMe(): Promise<User | null> {
  const r = await request(`${API}/b2c/me`);
  if (r.status === 401) return null;
  const body = await r.json();
  if (!r.ok) throw new ApiError(body.detail || "Hesap bilgileri yüklenemedi.", r.status, body.code || "");
  return body;
}

export async function authRequest(path: string, body?: Record<string, string>, method = "POST"): Promise<AuthResponse> {
  const r = await request(`/_allauth/browser/v1/${path}`, { method, headers: { "Content-Type": "application/json" }, ...(body ? { body: JSON.stringify(body) } : {}) });
  const data: AuthResponse = r.headers.get("content-type")?.includes("application/json") ? await r.json() : { status: r.status };
  if (r.status === 429) throw new ApiError("Çok fazla deneme yaptınız. Lütfen biraz bekleyip tekrar deneyin.", 429);
  if (r.status !== 401 && !r.ok) throw new ApiError(annotate(detailedMessage(data.errors) || (data as { detail?: string }).detail || statusMessage(r.status), r.status), r.status, data.errors?.[0]?.code || "");
  if (data.errors?.length) throw new ApiError(annotate(detailedMessage(data.errors), r.status), r.status, data.errors[0].code);
  await refreshCsrf();
  return data;
}

export async function resend(email: string) {
  const r = await request(`${API}/b2c/email/verification/request`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
  if (!r.ok) throw new ApiError(r.status === 429 ? "Çok fazla deneme yaptınız. Lütfen biraz bekleyin." : annotate("E-posta gönderilemedi. Lütfen tekrar deneyin.", r.status), r.status);
}
