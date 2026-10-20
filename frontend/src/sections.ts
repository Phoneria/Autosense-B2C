// Uygulama içi bölümler ve adresleri. Bölümler eskiden yalnızca sayfa içi
// durum (state) idi; artık her birinin paylaşılabilir bir adresi var.
export type Section = "analysis" | "guide" | "regional" | "profile";

export const SECTION_PATHS: Record<Section, string> = {
  analysis: "/",
  guide: "/rehber",
  regional: "/bolgesel",
  profile: "/hesabim",
};

export const APP_PATHS = Object.values(SECTION_PATHS);

export function sectionFromPath(pathname: string): Section {
  const clean = pathname.replace(/\/+$/, "") || "/";
  const hit = (Object.keys(SECTION_PATHS) as Section[]).find(key => SECTION_PATHS[key] === clean);
  return hit || "analysis";
}

/** Girişten sonra dönülecek adres: yalnızca uygulamanın kendi bölümleri kabul edilir. */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
  const path = value.split(/[?#]/)[0].replace(/\/+$/, "") || "/";
  return APP_PATHS.includes(path) ? value : "/";
}
