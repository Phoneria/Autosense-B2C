import type { DamageState } from "./types";

/** Hasar şeması: [alan adı, etiket, CSS grid-area]. Sıra araç şemasındaki
 *  yerleşimi belirler; grid-area isimleri styles.css'teki .car-map ile eşleşir. */
export const CAR_PARTS: [string, string, string][] = [
  ["on_tampon", "Ön tampon", "front"],
  ["sol_on_camurluk", "Sol ön çamurluk", "left-front"],
  ["motor_kaputu", "Kaput", "hood"],
  ["sag_on_camurluk", "Sağ ön çamurluk", "right-front"],
  ["sol_on_kapi", "Sol ön kapı", "left-door-front"],
  ["tavan", "Tavan", "roof"],
  ["sag_on_kapi", "Sağ ön kapı", "right-door-front"],
  ["sol_arka_kapi", "Sol arka kapı", "left-door-rear"],
  ["sag_arka_kapi", "Sağ arka kapı", "right-door-rear"],
  ["sol_arka_camurluk", "Sol arka çamurluk", "left-rear"],
  ["arka_kaput", "Bagaj", "trunk"],
  ["sag_arka_camurluk", "Sağ arka çamurluk", "right-rear"],
  ["arka_tampon", "Arka tampon", "rear"],
];

export const DAMAGE_CYCLE: DamageState[] = ["original", "local", "painted", "changed"];

export const DAMAGE_LABEL: Record<DamageState, string> = {
  original: "Orijinal",
  local: "Lokal boyalı",
  painted: "Boyalı",
  changed: "Değişen",
};

/** Backend'e gönderilen durum metni -- estimator bu tam ifadeleri bekliyor. */
export const DAMAGE_API_LABEL: Record<DamageState, string> = {
  original: "Orijinal",
  local: "Lokal Boyalı",
  painted: "Boyalı",
  changed: "Değişmiş",
};

export const DEFAULT_DAMAGE = Object.fromEntries(
  CAR_PARTS.map(([key]) => [key, "original" as DamageState]),
) as Record<string, DamageState>;

export const COLORS = [
  "Beyaz", "Siyah", "Gri / Gümüş", "Füme", "Mavi", "Lacivert", "Kırmızı",
  "Bordo", "Yeşil", "Kahverengi", "Bej", "Altın", "Şampanya", "Sarı",
  "Turuncu", "Mor", "Turkuaz", "Pembe", "Diğer",
];

export const CATEGORIES: [string, string][] = [
  ["otomobil", "Otomobil"],
  ["arazi-suv-pick-up", "Arazi / SUV / Pick-up"],
  ["minivan-panelvan", "Minivan / Panelvan"],
];

/** Yakıt ve vites seçenekleri -- B2B tarafıyla AYNI değer kümesi
 *  (frontend/src/config/filters.config.ts ve PriceEstimatePage.tsx).
 *  Serbest metin olarak bırakılırsa tahmin motoruna eşleşmeyen değer gidiyor. */
export const FUEL_OPTIONS = ["Benzin", "Dizel", "LPG & Benzin", "Hibrit", "Elektrik"];
export const GEAR_OPTIONS = ["Manuel", "Otomatik", "Yarı Otomatik"];

/** Motor/paket adından yakıt tipini çıkarır -- kullanıcı elle seçmesin diye
 *  ön doldurma amaçlı; kullanıcı isterse üzerine yazar. */
export function guessFuel(...parts: (string | undefined)[]): string {
  // DİKKAT: toLocaleLowerCase("tr-TR") KULLANMA. Türkçe kuralında "I" -> "ı"
  // (noktasız) olur, yani "TDI" -> "tdı" ve aşağıdaki latin motor kodlarının
  // hiçbiri eşleşmez (TDI, MPI, GDI, FSI, TSI...). Burada eşleştirilen şey
  // Türkçe kelime değil, latin motor kodu -- düz toLowerCase doğrusu.
  const text = parts.filter(Boolean).join(" ").toLowerCase();
  if (/\b(lpg|otogaz)\b/.test(text)) return "LPG & Benzin";
  if (/\b(plug[ -]?in|phev|hibrit|hybrid|e[ -]?tech|dm[ -]?i)\b/.test(text)) return "Hibrit";
  if (/\b(tdi|tdci|hdi|bluehdi|dci|cdi|crdi|multijet|jtd|dizel|diesel)\b/.test(text)) return "Dizel";
  if (/\b(tsi|tfsi|fsi|mpi|vti|puretech|ecoboost|tce|thp|gdi|t-gdi|mjt|skyactiv|vvt|dualjet|firefly|fire|e-torq|t-jet|benzin|petrol)\b/.test(text)) return "Benzin";
  if (/\b(elektrik|electric|e[ -]?tron|ev|taycan|ioniq|zoe|leaf)\b/.test(text)) return "Elektrik";
  if (/^(byd (seal|dolphin|han)|tesla|togg)\b/.test(text)) return "Elektrik";
  return "";
}
