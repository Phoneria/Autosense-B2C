import type { ListingTextResult, VehicleBrand } from "./types";

// The shared lookup API returns bare slugs for B2B. B2C selects catalog
// entries by their full slugs; resolve against the actual parent hierarchy.
export function resolveListingSelection(data: ListingTextResult, vehicles: VehicleBrand[]) {
  const find = <T extends { slug: string }>(items: T[] | undefined, slug: string, parent: string) =>
    slug ? items?.find((item) => item.slug === slug || item.slug === `${parent}-${slug}`) : undefined;
  const brand = vehicles.find((item) => item.category === data.category && item.slug === data.brand_slug);
  const series = find(brand?.series, data.series_slug, brand?.slug || "");
  const engine = find(series?.engines, data.engine_slug, series?.slug || "");
  const variants = engine?.variants?.length ? engine.variants : series?.variants;
  const variant = find(variants, data.variant_slug, engine?.variants?.length ? engine.slug : series?.slug || "");
  return { brand: brand?.slug || "", series: series?.slug || "", engine: engine?.slug || "", variant: variant?.slug || "" };
}
