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
