"""
Best-effort matching from a free-text vehicle name (e.g. the "Hızlı Satan
Araçlar" scan's tam_isim: "Renault Clio 1.0 TCe Evolution" — brand + series +
engine + variant all squashed into one string, no separators guaranteed) to
the brand_slug / series_slug / engine_slug / variant_slug fields that
build_arabam_url() and FilterPanel expect.

Approach: normalize both sides (lowercase, strip spaces/dots/dashes/&) and
greedily consume the normalized tam_isim from the front — brand name first,
then series name, then engine name, then variant name — each time picking
the *longest* candidate whose normalized name is a prefix of what's left.
This works well because tam_isim values in this app's data are themselves
derived from arabam.com's own model naming, so "Renault" + "Clio" + "1.0 TCe"
+ "Evolution" normalize to the exact same character sequence as the brand/
series/engine/variant "name" fields in arabam_brands.json.

Slugs are returned "bare" (parent prefix stripped), matching the convention
FilterPanel.tsx stores filters in (brand_slug="renault", series_slug="clio",
engine_slug="1-0-tce", variant_slug="evolution") — see bareSeriesSlug /
bareEngineSlug / bareVariantSlug in FilterPanel.tsx, mirrored here.
"""

from .arabam_vehicles_service import load_arabam_vehicles


def _norm(s: str) -> str:
    if not s:
        return ""
    # Buyuk Turkce "I" harfleri icin .casefold()/.lower() yanlis sonuc verir:
    # "İ".casefold() -> "i" + U+0307 COMBINING DOT ABOVE (tek "i" degil), ve
    # "I".casefold() -> "i" (dogru olan "ı" iken) -- ikisi de asagidaki
    # ıgcuosç foldundan *once*, ham string uzerinde elle cevriliyor.
    s = s.replace("İ", "i").replace("I", "ı")
    s = s.casefold()
    s = s.replace("̇", "")  # olası artakalan combining dot above
    for ch in (" ", ".", "-", "_", "&", "'", "’"):
        s = s.replace(ch, "")
    # Turkish-specific folds so "ı" etc. compare consistently
    s = (
        s.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ş", "s")
        .replace("ç", "c")
        .replace("ö", "o")
        .replace("ü", "u")
    )
    return s


def _bare(parent_prefix: str, slug: str) -> str:
    prefix = parent_prefix + "-"
    return slug[len(prefix):] if slug.startswith(prefix) else slug


def _best_prefix_match(remaining_norm: str, candidates: list):
    """Return the candidate dict whose normalized name is the *longest*
    prefix of remaining_norm, or None if nothing matches."""
    best = None
    best_len = 0
    for c in candidates:
        n = _norm(c["name"])
        if n and remaining_norm.startswith(n) and len(n) > best_len:
            best = c
            best_len = len(n)
    return best, best_len


def guess_arabam_match(tam_isim: str) -> dict:
    """
    Returns:
    {
      "matched": bool,             # at least brand+series resolved
      "category": "otomobil" | "arazi-suv-pick-up",
      "brand_slug": "renault", "brand_name": "Renault",
      "series_slug": "clio", "series_name": "Clio",
      "engine_slug": "1-0-tce", "engine_name": "1.0 TCe",   # "" if not resolved
      "variant_slug": "evolution", "variant_name": "Evolution",  # "" if not resolved
    }
    """
    empty = {
        "matched": False, "category": "otomobil",
        "brand_slug": "", "brand_name": "",
        "series_slug": "", "series_name": "",
        "engine_slug": "", "engine_name": "",
        "variant_slug": "", "variant_name": "",
    }
    if not tam_isim:
        return empty

    full_norm = _norm(tam_isim)
    brands = load_arabam_vehicles()

    best_result = None
    best_score = -1

    for brand in brands:
        brand_norm = _norm(brand.get("name", ""))
        if not brand_norm or not full_norm.startswith(brand_norm):
            continue
        remaining = full_norm[len(brand_norm):]

        series_match, series_len = _best_prefix_match(remaining, brand.get("series", []))
        score = len(brand_norm) + series_len
        # Prefer results that at least matched a series; among those, the
        # longest total consumed prefix wins (handles multi-word brands vs.
        # a shorter brand name that happens to also be a valid prefix).
        if series_match is None:
            if best_result is not None:
                continue
            candidate = {**empty, "matched": False,
                         "category": brand.get("category", "otomobil"),
                         "brand_slug": brand.get("slug", ""), "brand_name": brand.get("name", "")}
            if score > best_score:
                best_score = score
                best_result = candidate
            continue

        remaining2 = remaining[series_len:]
        # arabam.com ilan sayfalarinda seri adi genelde "<Seri> Serisi"
        # bicimindedir (orn. "E Serisi", "3 Serisi"), ama arabam_brands.json
        # icindeki "name" alaninda bu ek sadece bazi markalarda var (BMW/Audi
        # "1 Serisi" gibi) -- cogunlukla ("E", "C", "A" gibi) yok. Veri
        # setinde ek olmayan bir seri icin ilan metninde yine de "Serisi"
        # kelimesi gelirse remaining2'nin basinda kalip motor eslesmesini
        # engelliyordu (bkz. "Marka/model bulundu ama motor bilgisi
        # eslesmedi" hatasi). Veri setindeki adda zaten "serisi" yoksa,
        # kalan metnin basindaki bu kelimeyi (bosluksuz normalize haliyle)
        # tuketip devam ediyoruz.
        if "serisi" not in _norm(series_match.get("name", "")) and remaining2.startswith("serisi"):
            remaining2 = remaining2[len("serisi"):]
        engine_match, engine_len = _best_prefix_match(remaining2, series_match.get("engines", []))

        engine_slug = engine_name = variant_slug = variant_name = ""
        if engine_match:
            remaining3 = remaining2[engine_len:]
            variant_match, variant_len = _best_prefix_match(remaining3, engine_match.get("variants", []))
            engine_slug = _bare(series_match.get("slug", ""), engine_match.get("slug", ""))
            engine_name = engine_match.get("name", "")
            if variant_match:
                variant_slug = _bare(engine_match.get("slug", ""), variant_match.get("slug", ""))
                variant_name = variant_match.get("name", "")
            score += engine_len + variant_len
        else:
            score += 0

        candidate = {
            "matched": True,
            "category": brand.get("category", "otomobil"),
            "brand_slug": brand.get("slug", ""),
            "brand_name": brand.get("name", ""),
            "series_slug": _bare(brand.get("slug", ""), series_match.get("slug", "")),
            "series_name": series_match.get("name", ""),
            "engine_slug": engine_slug,
            "engine_name": engine_name,
            "variant_slug": variant_slug,
            "variant_name": variant_name,
        }
        # A matched series always outranks a brand-only match, and among
        # matched candidates the longest consumed prefix wins.
        score += 100000
        if score > best_score:
            best_score = score
            best_result = candidate

    return best_result if best_result is not None else empty
