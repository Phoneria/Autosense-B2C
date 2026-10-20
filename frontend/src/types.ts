// Backend sözleşmesi -- Backend/search/services/b2c.py::analyze() ile birebir.
// Bir alan burada değişirse orada da değişmeli.

export type DamageState = "original" | "local" | "painted" | "changed";

export interface VehicleVariant { slug: string; name: string }
export interface VehicleEngine { slug: string; name: string; variants?: VehicleVariant[] }
export interface VehicleSeries { slug: string; name: string; engines: VehicleEngine[]; variants?: VehicleVariant[] }
export interface VehicleBrand { slug: string; name: string; category: string; series: VehicleSeries[] }

export interface LocationOption { city: string; districts: string[] }

export interface TrendPoint { snapshot_date: string; avg_price: number; sample_count: number }

export interface PriceFactor { label: string; note: string; effect_pct: number }

export interface Contradiction { claim: string; conflict: string }

/** Açıklamadan çıkan sinyallerin fiyata toplam etkisi (b2c.py::_compute_price_impact). */
export interface PriceImpact {
  total_pct: number;
  rules: { key: string; label: string; pct: number }[];
  base_price: number | null;
  adjusted_price: number | null;
  delta: number | null;
}

export interface DescriptionAnalysis {
  available: boolean;
  score: number;
  label: string;
  summary: string;
  claims: { key: string; label: string }[];
  contradictions: Contradiction[];
  red_flags: string[];
  positives: string[];
  missing: string[];
  km_claims: number[];
  suggestions?: string[];
  price_impact?: PriceImpact | null;
}

export interface SimilarListing {
  title: string;
  model: string;
  year: number;
  km: number | null;
  color: string | null;
  price: number;
  url: string | null;
  gallery: string | null;
  city: string | null;
  district: string | null;
  post_age_days: number | null;
  price_diff: number | null;
}

export interface AnalysisResult {
  generated_at: string;
  vehicle: {
    brand: string; series: string; engine: string; package: string | null;
    year: number; km: number; color: string | null;
    city: string; district: string; price: number;
  };
  estimate: {
    tahmini_fiyat: number | null;
    estimated_low: number | null;
    estimated_high: number | null;
    confidence_pct: number;
    color_adjustment: { color: string; factor_pct: number; sample_count: number } | null;
    fallback_reason: string | null;
    /** Paket seçilmediğinde: kaç paketin tahmini medyanlandı. */
    package_fallback: { count: number; packages: string[] } | null;
    /** Son 30 günün liste ilanlarından gelen güncel piyasa bileşeni. */
    liste?: { count: number; weight: number; period: [string, string] | null } | null;
  };
  decision: { label: string; title: string; score: number; deviation_pct: number };
  negotiation: {
    available: boolean; reason: string; note: string;
    target_price: number | null; opening_offer: number | null;
    ceiling_price: number | null; potential_saving: number | null;
  };
  depreciation: {
    available: boolean; reason: string; note: string;
    current_value: number | null;
    one_year_value: number | null; one_year_loss: number | null;
    three_year_value: number | null; three_year_loss: number | null;
  };
  listing_quality: {
    label: string; score: number; warnings: string[];
    /** Her uyarının 100 üzerinden götürdüğü puan; warnings ile aynı sırada. */
    deductions: { label: string; points: number }[];
  };
  description_analysis: DescriptionAnalysis;
  similar_listings: SimilarListing[];
  questions: { question: string; reason: string }[];
  price_factors: PriceFactor[];
  price_trend: TrendPoint[];
  regional_signal: {
    city: string; district: string; label: string; confidence_pct: number;
    /** İl ortalamasının ülke ortalamasına yüzde farkı; veri yoksa null. */
    delta_pct: number | null;
  };
  tco: {
    yillik_km_varsayimi: number;
    toplam_yillik_tl: number;
    mtv: { yillik_tl: number | null; not: string | null };
    yakit: { yillik_tl: number };
    sigorta: { yillik_tl: number };
    bakim: { yillik_tl: number };
  };
  data_sources: {
    gallery_matches: number; listing_matches: number;
    trend_points: number; similar_listings: number;
  } | null;
  vehicle_traits: VehicleTraits;
  evidence: Evidence;
  billing?: Billing;
  plan?: string;
  /** Plana göre kilitlenen bölümler: verisi gönderilmez, sadece bu bilgi gelir. */
  locks?: Record<string, PlanLock>;
}

export interface PlanLock {
  feature: string;
  required_plan: "pro" | "premium";
  required_plan_name: string;
  current_plan: string;
  current_plan_name: string;
  count: number | null;
}

/** Tahminin arkasındaki kanıt (b2c.py::_evidence). */
export interface Evidence {
  strength: "strong" | "medium" | "weak";
  locked?: boolean;
  trim_match: "exact" | "engine" | "engine_median" | "none";
  reference_listings: number;
  gear_specific: boolean;
  unique_comparables: number;
  unique_sellers: number;
  same_year_comparables: number;
  live_comparables: number;
  window_days: number;
  data_date: string | null;
  data_age_days: number | null;
  notes: string[];
}

export interface Billing {
  plan: string;
  plan_name: string;
  quota: number;
  credits: number;
  extra_credits: number;
  total_credits: number;
  next_reset_at: string;
  reset_minutes: number;
  plan_features: string[];
  /** true: tüm özellikler açık, analiz kredi harcamaz (B2C_OPEN_ACCESS). */
  open_access?: boolean;
  /** true: plan kredisi sınırsız (Premium). */
  unlimited?: boolean;
}

export interface PlanOption { id: string; name: string; credits: number; price_label: string; features: string[] }
export interface BillingDetails extends Billing {
  plans: PlanOption[];
  credit_packs: { amount: number; price_label: string }[];
}

export interface ScenarioResult {
  estimate: {
    tahmini_fiyat: number | null; estimated_low: number | null; estimated_high: number | null;
    confidence_pct: number; fallback_reason: string | null;
  };
  decision: AnalysisResult["decision"];
  negotiation: AnalysisResult["negotiation"];
}

export interface CostLine { key: string; label: string; yearly_tl: number; monthly_tl: number; estimated: boolean; note: string | null }
export interface CostResult {
  fuel: string; engine_cc: number | null; annual_km: number;
  lines: CostLine[]; total_yearly_tl: number; total_monthly_tl: number;
  per_km_tl: number | null; estimated_count: number;
}

/** Tek bir kronik / iyi / kötü kaydı (backend: search/services/vehicle_traits.py). */
export interface VehicleTrait {
  etiket: string;
  iddia: string;
  km_araligi: string | null;
  kaynak_url: string | null;
  kaynak_alan: string | null;
  kaynak_alinti: string | null;
  guven: "yuksek" | "orta" | "dusuk";
}

export interface VehicleTraits {
  available: boolean;
  anahtar: string;
  etiket: string;
  yil_baslangic: number | null;
  yil_bitis: number | null;
  kaynak_n: number;
  kronik: VehicleTrait[];
  iyi: VehicleTrait[];
  kotu: VehicleTrait[];
}

/** Seçim kutusundaki bir satır. */
export interface TraitVehicleOption {
  anahtar: string;
  etiket: string;
  marka: string;
  seri: string;
  motor: string;
  yil_baslangic: number | null;
  yil_bitis: number | null;
  kronik_n: number;
  iyi_n: number;
  kotu_n: number;
}

export interface ListingTextResult {
  warnings?: string[];
  matched: boolean;
  category: string;
  brand_slug: string;
  series_slug: string;
  engine_slug: string;
  variant_slug: string;
  year: number | null;
  km: number | null;
  price: number | null;
  city: string;
  district: string;
  fuel: string;
  color: string;
  description: string;
  gear: string;
  agir_hasar: boolean;
  damage_map: Record<string, string>;
}

export interface RegionalListing {
  title: string; engine: string | null; year: number; km: number; price: number; estimate: number;
  url: string | null; dealer: string; post_age_days: number | null; color: string | null; below_market_pct: number;
}
export interface RegionalDeal {
  city: string; model: string; brand: string; series: string; category: string;
  diff_pct: number; listings: number; dealers: number; country_listings: number;
  median_price: number; country_median_price: number; median_year: number; median_km: number; min_price: number;
  top_listings: RegionalListing[];
}
export interface RegionalCityStat {
  city: string; avg_diff_pct: number; models_compared: number; cheaper_models: number; listings: number; dealers: number;
}
export interface RegionalOverview {
  snapshot_date: string | null;
  priced_listings?: number;
  thresholds: { min_listings: number; min_dealers: number; min_country_listings: number };
  cities: RegionalCityStat[];
  deals: RegionalDeal[];
  listings_lock?: PlanLock;
}

export interface GuideSummary {
  key: string; name: string; category: string; active: number; removed_30d: number;
  median_price: number | null; median_days_on_market: number | null;
  price_change_4w_pct: number | null; turnover_pct: number | null;
}
export interface GuideHome {
  plan?: string;
  snapshot_date: string; first_date: string; snapshot_count: number; window_days: number; premium: boolean;
  home: { most_demand: GuideSummary[]; fastest: GuideSummary[]; rising: GuideSummary[]; falling: GuideSummary[]; most_listed: GuideSummary[] };
  models: { key: string; name: string; category: string; active: number; removed_30d: number; has_traits: boolean }[];
}
export interface GuideWeekly {
  stock: number[]; new: (number | null)[]; removed: (number | null)[];
  median_price: (number | null)[]; price_index: (number | null)[]; samples: number[];
}
export interface GuideModel extends GuideSummary {
  brand: string; series: string; dealers: number; new_30d: number;
  trait_engines: { key: string; label: string; listings: number; kronik: number; iyi: number; kotu: number }[];
  snapshot_date: string; window_days: number; premium: boolean;
  weeks?: string[]; weekly?: GuideWeekly; lock?: PlanLock;
  similar?: { key: string; name: string; median_price: number; active: number; removed_30d: number; price_change_4w_pct: number | null }[];
}
export interface GuideCompare {
  weeks: string[];
  models: { key: string; name: string; weekly: GuideWeekly; median_price: number | null; removed_30d: number; active: number; median_days_on_market: number | null; price_change_4w_pct: number | null }[];
}
