import type { AnalysisResult, ListingTextResult, LocationOption, VehicleBrand } from "./types";
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
