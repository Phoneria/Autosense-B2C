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
  listing_quality: { label: string; score: number; warnings: string[] };
  description_analysis: DescriptionAnalysis;
  similar_listings: SimilarListing[];
  questions: { question: string; reason: string }[];
  price_factors: PriceFactor[];
  price_trend: TrendPoint[];
  regional_signal: { city: string; district: string; label: string; confidence_pct: number };
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
  };
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
