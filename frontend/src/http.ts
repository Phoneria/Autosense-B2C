export const API = "/api";
export class ApiError extends Error {
  constructor(message: string, public status: number, public code = "") { super(message); }
}
let csrfToken = "";
let csrfPending: Promise<string> | null = null;
export async function refreshCsrf(): Promise<string> {
  if (!csrfPending) csrfPending = fetch(`${API}/b2c/csrf`, { credentials: "same-origin", cache: "no-store" })
    .then(async r => { if (!r.ok) throw new ApiError("Güvenli bağlantı kurulamadı. Lütfen tekrar deneyin.", r.status); const data = await r.json(); csrfToken = data.csrfToken; if (!csrfToken) throw new Error("Güvenli bağlantı kurulamadı."); return csrfToken; })
    .finally(() => { csrfPending = null; });
  return csrfPending;
}
export async function request(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const unsafe = !["GET", "HEAD", "OPTIONS"].includes((init.method || "GET").toUpperCase());
  try {
    if (unsafe) headers.set("X-CSRFToken", csrfToken || await refreshCsrf());
    const send = () => fetch(url, { ...init, headers, credentials: "same-origin", cache: "no-store" });
    const response = await send();
    // A CSRF rejection means the server did not execute the operation. Refresh
    // once for another tab's rotated cookie; never replay another kind of error.
    if (unsafe && response.status === 403 && response.headers.get("content-type")?.includes("application/json")) {
      const body = await response.clone().json().catch(() => null);
      if (body?.code === "csrf_failed") {
        headers.set("X-CSRFToken", await refreshCsrf());
        return await send();
      }
    }
    return response;
  } catch (error) {
    if (error instanceof ApiError || error instanceof DOMException && error.name === "AbortError") throw error;
    throw new Error("Sunucuya ulaşılamıyor. Bağlantınızı kontrol edip tekrar deneyin.");
  }
}
export async function json<T>(response: Response, fallback: string): Promise<T> {
  const body = response.headers.get("content-type")?.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const code = body?.code || "";
    if (response.status === 401 || code === "not_authenticated") window.dispatchEvent(new Event("auth:expired"));
    if (code === "email_unverified" || code === "email_verification_required") window.dispatchEvent(new Event("auth:unverified"));
    throw new ApiError(response.status === 429 ? "Çok fazla deneme yaptınız. Lütfen biraz bekleyip tekrar deneyin." : body?.error || body?.detail || fallback, response.status, code);
  }
  if (body === null) throw new Error(fallback);
  return body as T;
}
