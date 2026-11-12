import type { Billing } from "./types";

/** Liste fiyatları. Backend de aynı değerleri döndürür; burada ekranın
 *  backend güncellenene kadar da doğru fiyatı göstermesi için tutuluyor. */
export const PLAN_PRICES: Record<string, string> = {
  basic: "Ücretsiz",
  pro: "₺499 / ay",
  premium: "₺2.999 / ay",
};

export const priceOf = (id: string, fallback: string) => PLAN_PRICES[id] || fallback;

/** Premium planda analiz sınırı yok. */
export const isUnlimited = (b?: Pick<Billing, "plan" | "unlimited"> | null) =>
  !!b && (b.unlimited || b.plan === "premium");

export const planLabel = (id?: string, name?: string) =>
  name || (id ? id.charAt(0).toUpperCase() + id.slice(1) : "Basic");

export function resetLabel(iso?: string) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("tr-TR", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
}

/** Giriş yapmamış ziyaretçiye gösterilen plan kataloğu. Backend'deki
 *  accounts/billing.py PLANS ile aynı tutulmalı (fiyat, kredi, özellikler). */
export interface PublicPlan { id: "basic" | "pro" | "premium"; name: string; credits: number; price_label: string; features: string[] }
export const PUBLIC_PLANS: PublicPlan[] = [
  { id: "basic", name: "Basic", credits: 3, price_label: "Ücretsiz", features: ["Günde 3 analiz", "Analiz sayfası"] },
  { id: "pro", name: "Pro", credits: 15, price_label: "₺499 / ay",
    features: ["Günde 15 analiz", "Ne olurdu? senaryoları", "Değer kaybı ve tahmin detayları", "Araç Rehberi ve Bölgesel fırsatlar (özet)"] },
  { id: "premium", name: "Premium", credits: 50, price_label: "₺2.999 / ay",
    features: ["Sınırsız analiz", "Pro'daki her şey", "Yayındaki benzer ilanlar",
      "Araç Rehberi model sayfası: fiyat/satış grafikleri, karşılaştırma", "Bölgesel fırsatların arkasındaki gerçek ilanlar"] },
];

export const VAT_NOTE = "Fiyatlara KDV dahildir.";

/** "Satın Al"a basan ziyaretçi kayıt/giriş yaptıktan sonra seçtiği planın
 *  sipariş özetine dönsün diye plan geçici olarak saklanır (e-posta kodu ve
 *  Google girişi de aynı sekmede kaldığı için sessionStorage yeterli). */
const PENDING_KEY = "b2c:pending-plan";
const PENDING_TTL_MS = 60 * 60 * 1000;
export type PaidPlan = "pro" | "premium";

export function savePendingPlan(plan: PaidPlan) {
  try { sessionStorage.setItem(PENDING_KEY, JSON.stringify({ plan, at: Date.now() })); } catch { /* depolama kapalı */ }
}

export function takePendingPlan(): PaidPlan | null {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    sessionStorage.removeItem(PENDING_KEY);
    if (!raw) return null;
    const { plan, at } = JSON.parse(raw) as { plan?: string; at?: number };
    if (!at || Date.now() - at > PENDING_TTL_MS) return null;
    return plan === "pro" || plan === "premium" ? plan : null;
  } catch { return null; }
}
