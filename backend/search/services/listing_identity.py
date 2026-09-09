"""Resolve structured listing identity against the catalog, independent of site labels."""
import re

from .arabam_vehicles_service import load_arabam_vehicles
from .model_name_matcher import _norm, _bare


CATEGORIES = {
    "otomobil": "otomobil", "arazisuvpickup": "arazi-suv-pick-up",
    "minivanpanelvan": "minivan-panelvan",
}


def _paths(lines):
    """Both slash-separated photo paths and the vertical navigation path."""
    paths = set()
    for i, line in enumerate(lines):
        parts = [part.strip() for part in line.split("/")]
        if _norm(parts[0]) != "vasita":
            continue
        if len(parts) == 1:
            parts = [line]
            for following in lines[i + 1:i + 8]:
                if _norm(following) in {"favoriilanlarim", "favoriaramalarim", "karsilastir"}:
                    break
                parts.append(following)
        if len(parts) >= 4 and _norm(parts[1]) in CATEGORIES:
            paths.add((CATEGORIES[_norm(parts[1])], parts[2], tuple(parts[3:])))
    return sorted(paths)


def resolve_listing_identity(fields, lines):
    catalog = load_arabam_vehicles()
    brand_name = fields["marka"]
    paths = _paths(lines)
    if not brand_name:
        names = {_norm(name): name for _, name, _ in paths}
        if len(names) == 1:
            brand_name = next(iter(names.values()))
    empty = {"matched": False, "category": "otomobil"}
    for level in ("brand", "series", "engine", "variant"):
        empty[level + "_slug"] = empty[level + "_name"] = ""
    evidence = [(None, (fields["seri"], fields["model"]))]
    evidence += [(cat, parts) for cat, name, parts in paths if _norm(name) == _norm(brand_name)]
    candidates = []
    for brand in catalog:
        if _norm(brand["name"]) != _norm(brand_name):
            continue
        base = {**empty, "category": brand.get("category", "otomobil"),
                "brand_slug": brand["slug"], "brand_name": brand["name"]}
        candidates.append(((0, 0, 0), base, "", (-1, brand["slug"], base["category"])))
        for evidence_index, (category, chunks) in enumerate(evidence):
            evidence_key = (evidence_index, brand["slug"], base["category"])
            if category and category != base["category"]:
                continue
            chunks = [chunk for chunk in chunks if chunk]
            for series in brand.get("series", []):
                series_norm = _norm(series["name"])
                for index, chunk in enumerate(chunks):
                    # A series must start a field/path segment, never seller prose.
                    value = _norm(chunk)
                    if not value.startswith(series_norm):
                        continue
                    rest = value[len(series_norm):]
                    if rest.startswith("serisi") and not series_norm.endswith("serisi"):
                        rest = rest[6:]
                    remaining = rest + "".join(_norm(c) for j, c in enumerate(chunks) if j != index)
                    found_series = {**base, "matched": True, "series_name": series["name"],
                                    "series_slug": _bare(brand["slug"], series["slug"])}
                    candidates.append(((1, 0, len(series_norm)), found_series, "", evidence_key))
                    # Try exact engine spelling first. A separate diesel marker
                    # between displacement and engine code is optional on some sites.
                    alternate_chunks = [re.sub(r"(\d+[.,]\d+)\s+D\s+(?=[A-Z]\d)", r"\1 ", c, flags=re.I) for c in chunks]
                    alternate = _norm(alternate_chunks[index])[len(series_norm):] + "".join(
                        _norm(c) for j, c in enumerate(alternate_chunks) if j != index)
                    forms = [(remaining, 0)]
                    if "dizel" in _norm(fields.get("yakit", "")) and alternate != remaining:
                        forms.append((alternate, 1))
                    for engine in series.get("engines", []):
                        engine_norm = _norm(engine["name"])
                        for form, alias in forms:
                            if engine_norm not in form:
                                continue
                            residue = form.replace(engine_norm, "", 1)
                            variants = engine.get("variants") or series.get("variants", [])
                            variant = next((v for v in variants if _norm(v["name"]) == residue and residue), None)
                            found = {**found_series, "engine_name": engine["name"],
                                     "engine_slug": _bare(series["slug"], engine["slug"])}
                            if variant:
                                parent = engine["slug"] if engine.get("variants") else series["slug"]
                                found.update(variant_name=variant["name"], variant_slug=_bare(parent, variant["slug"]))
                            # Complete consumption outranks substring matches;
                            # exact spelling wins over optional-marker matching.
                            score = (2 + int(not residue or variant is not None), -alias,
                                     len(series_norm) + len(engine_norm) + (len(residue) if variant else 0))
                            warning = ""
                            if residue and not variant:
                                package = chunks[-1] if category and len(chunks) >= 3 else ""
                                warning = (f"İlandaki {package} paketi katalogda bulunamadı; paket alanını kontrol edin." if package
                                           else "Model/paket bilgisinin bir bölümü katalogla eşleşmedi; paket alanını kontrol edin.")
                            candidates.append((score, found, warning, evidence_key))
    if not candidates:
        return empty, []
    # Longest catalog consumption disambiguates within one source. Across
    # independent sources, a longer model name is not stronger evidence.
    source_scores = {}
    for candidate in candidates:
        source_scores[candidate[3]] = max(source_scores.get(candidate[3], (-1, 0, 0)), candidate[0])
    winners = [c for c in candidates if c[0] == source_scores[c[3]]]
    confidence = max(c[0][:2] for c in winners)
    best = [c for c in winners if c[0][:2] == confidence]
    result = dict(best[0][1])
    warnings = sorted({c[2] for c in best if c[2]})
    if any(w.startswith("İlandaki ") for w in warnings):
        warnings = [w for w in warnings if not w.startswith("Model/paket ")]
    # Equal evidence for different identities: retain only their shared parents.
    for level in ("category", "brand", "series", "engine", "variant"):
        key = level if level == "category" else level + "_slug"
        if len({c[1][key] for c in best}) > 1:
            levels = ["brand", "series", "engine", "variant"]
            for child in levels[1 if level == "category" else levels.index(level):]:
                result[child + "_name"] = result[child + "_slug"] = ""
            warnings.append("Araç bilgileri birden fazla katalog seçeneğiyle eşleşiyor; belirsiz alanları elle seçin.")
            break
    result["matched"] = bool(result["series_slug"])
    return result, warnings
