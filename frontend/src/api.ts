import type {
  BillingDetails, CostResult, GuideCompare, GuideHome, GuideModel, RegionalOverview, ScenarioResult,
  AnalysisResult, ListingTextResult, LocationOption, TraitVehicleOption,
  VehicleBrand, VehicleTraits,
} from "./types";
import { API, request, json, ApiError } from "./http";
export { API } from "./http";

export async function fetchVehicles(): Promise<VehicleBrand[]> {
  const r = await request(`${API}/arabam-vehicles`);
  return json<VehicleBrand[]>(r, "Araç seçenekleri yüklenemedi.");
}

export async function fetchLocations(): Promise<LocationOption[]> {
  const r = await request(`${API}/b2c/locations`);
  return json<LocationOption[]>(r, "İl ve ilçe seçenekleri yüklenemedi.");
}

export async function fetchGearDefault(
  body: { category: string; brand: string; series: string; engine: string; package: string | null },
  signal?: AbortSignal,
): Promise<string> {
  try {
    const r = await request(`${API}/b2c/vehicle-defaults`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    const data = await json<{ gear_default?: string }>(r, "Araç varsayılanları yüklenemedi.");
    return data?.gear_default || "";
  } catch (error) {
    if (error instanceof ApiError && [401, 403, 429].includes(error.status)) throw error;
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    return "";                 // varsayılan bulunamazsa kullanıcı elle seçer
  }
}

export async function analyze(payload: Record<string, unknown>): Promise<AnalysisResult> {
  const r = await request(`${API}/b2c/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return json<AnalysisResult>(r, "Analiz tamamlanamadı.");
}

export async function lookupListingText(text: string): Promise<ListingTextResult> {
  const r = await request(`${API}/b2c/lookup-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return json<ListingTextResult>(r, "İlan metni okunamadı.");
}

/** Seçim kutusu için veri bulunan araçların listesi. */
export async function fetchTraitVehicles(signal?: AbortSignal): Promise<TraitVehicleOption[]> {
  const r = await request(`${API}/b2c/vehicle-traits`, { signal });
  const data = await json<{ vehicles: TraitVehicleOption[] }>(r, "Araç özellik listesi yüklenemedi.");
  return data?.vehicles || [];
}

/** Tek bir aracın kronik / iyi / kötü özellikleri. */
export async function fetchVehicleTraits(key: string, signal?: AbortSignal): Promise<VehicleTraits> {
  const r = await request(`${API}/b2c/vehicle-traits?key=${encodeURIComponent(key)}`, { signal });
  return json<VehicleTraits>(r, "Araç özellikleri yüklenemedi.");
}

export async function fetchBilling(): Promise<BillingDetails> {
  const r = await request(`${API}/b2c/account/billing`);
  return json<BillingDetails>(r, "Plan bilgileri yüklenemedi.");
}

export async function choosePlan(plan: string): Promise<BillingDetails> {
  const r = await request(`${API}/b2c/account/plan`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan }),
  });
  return json<BillingDetails>(r, "Plan değiştirilemedi.");
}

export async function runScenario(payload: Record<string, unknown>): Promise<ScenarioResult> {
  const r = await request(`${API}/b2c/scenario`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  return json<ScenarioResult>(r, "Senaryo hesaplanamadı.");
}

export async function calculateCost(payload: Record<string, unknown>): Promise<CostResult> {
  const r = await request(`${API}/b2c/cost`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  return json<CostResult>(r, "Maliyet hesaplanamadı.");
}

export async function fetchRegional(): Promise<RegionalOverview> {
  const r = await request(`${API}/b2c/regional-deals`);
  return json<RegionalOverview>(r, "Bölgesel veriler yüklenemedi.");
}

export async function fetchGuide(): Promise<GuideHome> {
  const r = await request(`${API}/b2c/guide`);
  return json<GuideHome>(r, "Araç rehberi yüklenemedi.");
}

export async function fetchGuideModel(key: string): Promise<GuideModel> {
  const r = await request(`${API}/b2c/guide/model?key=${encodeURIComponent(key)}`);
  return json<GuideModel>(r, "Model bilgileri yüklenemedi.");
}

export async function fetchGuideCompare(keys: string[]): Promise<GuideCompare> {
  const r = await request(`${API}/b2c/guide/compare?keys=${encodeURIComponent(keys.join(","))}`);
  return json<GuideCompare>(r, "Karşılaştırma yüklenemedi.");
}
