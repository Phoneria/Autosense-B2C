import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/listingText.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { resolveListingSelection } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const vehicles = ["arabam_brands.json", "arabam_brands_ticari.json"].flatMap((name) =>
  JSON.parse(readFileSync(new URL(`../../backend/search/data/${name}`, import.meta.url), "utf8")));

for (const [category, brand, series, engine, variant] of [
  ["otomobil", "bmw", "3-serisi", "320d", "standart"],
  ["otomobil", "bmw", "3-serisi", "320d", "m-sport"],
  ["otomobil", "dacia", "sandero", "1-5-dci", "ambiance"],
  ["arazi-suv-pick-up", "volvo", "xc90", "2-0-b5", "plus-bright"],
  ["minivan-panelvan", "chrysler", "grand-voyager", "2-8-crd-limited", ""],
]) {
  test(`${brand} ${series} ${engine} ${variant} resolves to selectable catalog values`, () => {
    const data = { category, brand_slug: brand, series_slug: series, engine_slug: engine, variant_slug: variant };
    const expected = { brand, series: `${brand}-${series}`, engine: `${brand}-${series}-${engine}`,
      variant: variant ? `${brand}-${series}-${engine}-${variant}` : "" };
    assert.deepEqual(resolveListingSelection(data, vehicles), expected);
    assert.deepEqual(resolveListingSelection({ ...data, series_slug: expected.series,
      engine_slug: expected.engine, variant_slug: expected.variant }, vehicles), expected);
    assert.equal(resolveListingSelection({ ...data, engine_slug: "unknown", variant_slug: "unknown" }, vehicles).engine, "");
  });
}
