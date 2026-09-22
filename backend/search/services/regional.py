"""Bölgesel fırsatlar (Premium).

Aynı model, bir ilçede şehir geneline göre daha mı ucuz? Ham fiyat ortalaması
yanıltır (ilçelerin araç yaşı/km profili farklı), bu yüzden her ilan önce
AutoSense tahminiyle fiyatlanır ve "fiyat oranı" (ilan fiyatı / tahmin)
hesaplanır. İlin o modeldeki (marka + seri) medyan oranı, ÜLKENİN GERİ KALANINDAKİ aynı
modelin medyan oranıyla kıyaslanır. Motor/yıl/km farkı oranın içinde zaten
normalize edildiği için gruplama seri seviyesinde yapılır.

Kaynak: galeri.db'nin EN SON snapshot'ı (galeri ilanları, ilan fiyatları).
İl = galerinin bulunduğu il. Sonuç snapshot tarihine göre önbelleğe alınır.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections import defaultdict
from pathlib import Path
from statistics import median

from django.conf import settings

from .b2c import _MAX_REAL_PRICE, _MIN_REAL_PRICE, _galeri_conn
from .price_estimator import estimate_listing, parse_listing_identity

logger = logging.getLogger(__name__)

MIN_GROUP_LISTINGS = 5      # il-model grubunda en az ilan
MIN_GROUP_DEALERS = 2       # tek galeri ili tek başına belirlemesin
MIN_CITY_LISTINGS = 8       # ülkenin geri kalanında kıyas için en az ilan
RATIO_BOUNDS = (0.5, 1.8)   # uç değerler (hatalı eşleşme / sahte fiyat) dışarıda
TOP_LISTINGS = 8

_lock = threading.Lock()
_memo: dict = {}


def _cache_path() -> Path:
    return Path(getattr(settings, "B2C_REGIONAL_CACHE", settings.PROJECT_DIR / ".local/regional_deals.json"))


def _latest_snapshot() -> str | None:
    try:
        return _galeri_conn().execute("SELECT MAX(snapshot_date) FROM gallery_listings").fetchone()[0]
    except Exception:
        return None


def _int(raw) -> int | None:
    digits = re.sub(r"\D", "", str(raw or ""))
    return int(digits) if digits else None


def build(snapshot: str | None = None) -> dict:
    snapshot = snapshot or _latest_snapshot()
    if not snapshot:
        return {"snapshot_date": None, "cities": []}
    rows = _galeri_conn().execute(
        """
        SELECT gl.listing_key, gl.gallery_name, gl.model, gl.title, gl.year_raw, gl.km_raw,
               gl.price, gl.post_url, gl.post_age_days, gl.color, g.city, g.district
          FROM gallery_listings gl
          JOIN galleries g ON g.gallery_name = gl.gallery_name
         WHERE gl.snapshot_date = ? AND gl.price BETWEEN ? AND ?
           AND g.city IS NOT NULL AND g.city != '' AND g.district IS NOT NULL AND g.district != ''
        """,
        (snapshot, _MIN_REAL_PRICE, _MAX_REAL_PRICE),
    ).fetchall()

    seen: set[str] = set()
    priced: list[dict] = []
    for key, gallery, model, title, year_raw, km_raw, price, url, age, color, city, district in rows:
        if key in seen:
            continue
        seen.add(key)
        year = _int(year_raw)
        km = _int(km_raw)
        if not model or not year or km is None or not 1950 <= year <= 2100:
            continue
        try:
            est = estimate_listing(model, year, km)
        except Exception:
            continue
        value = est.get("tahmini_fiyat")
        if not est.get("found") or not value:
            continue
        ratio = float(price) / float(value)
        if not RATIO_BOUNDS[0] <= ratio <= RATIO_BOUNDS[1]:
            continue
        ident = parse_listing_identity(model)
        priced.append({
            "city": city.strip(), "district": district.strip(), "dealer": gallery,
            "model": " ".join(x for x in (ident["brand"], ident["series"]) if x and x != "bilinmiyor"),
            "engine": ident["engine"] if ident["engine"] != "bilinmiyor" else None,
            "brand": ident["brand"], "series": ident["series"], "category": ident["category"],
            "title": (title or model).strip(), "year": year, "km": km, "price": int(price),
            "estimate": int(value), "ratio": ratio, "url": url or None,
            "post_age_days": age, "color": (color or "").strip() or None,
        })

    by_model: dict[str, list[dict]] = defaultdict(list)
    for item in priced:
        by_model[item["model"]].append(item)

    deals = []
    for model, members in by_model.items():
        by_city: dict[str, list[dict]] = defaultdict(list)
        for item in members:
            by_city[item["city"]].append(item)
        for city, rows in by_city.items():
            others = [m for m in members if m["city"] != city]
            dealers = {m["dealer"] for m in rows}
            if len(rows) < MIN_GROUP_LISTINGS or len(dealers) < MIN_GROUP_DEALERS or len(others) < MIN_CITY_LISTINGS:
                continue
            diff_pct = (median(m["ratio"] for m in rows) / median(m["ratio"] for m in others) - 1) * 100
            first = rows[0]
            deals.append({
                "city": city, "model": model, "brand": first["brand"], "series": first["series"],
                "category": first["category"],
                "diff_pct": round(diff_pct, 1),
                "listings": len(rows), "dealers": len(dealers), "country_listings": len(others),
                "median_price": int(median(m["price"] for m in rows)),
                "country_median_price": int(median(m["price"] for m in others)),
                "median_year": int(median(m["year"] for m in rows)),
                "median_km": int(median(m["km"] for m in rows)),
                "min_price": min(m["price"] for m in rows),
                "top_listings": [
                    {k: m[k] for k in ("title", "engine", "year", "km", "price", "estimate", "url", "dealer", "post_age_days", "color")}
                    | {"below_market_pct": round((1 - m["ratio"]) * 100, 1)}
                    for m in sorted(rows, key=lambda m: m["ratio"])[:TOP_LISTINGS]
                ],
            })
    deals.sort(key=lambda d: d["diff_pct"])

    city_stats: dict[str, dict] = {}
    for d in deals:
        stat = city_stats.setdefault(d["city"], {"city": d["city"], "weighted": 0.0, "weight": 0, "models": 0, "cheaper_models": 0})
        stat["weighted"] += d["diff_pct"] * d["listings"]
        stat["weight"] += d["listings"]
        stat["models"] += 1
        stat["cheaper_models"] += 1 if d["diff_pct"] < 0 else 0
    listing_counts: dict[str, int] = defaultdict(int)
    dealer_sets: dict[str, set] = defaultdict(set)
    for item in priced:
        listing_counts[item["city"]] += 1
        dealer_sets[item["city"]].add(item["dealer"])
    cities = sorted(
        ({"city": stat["city"], "avg_diff_pct": round(stat["weighted"] / stat["weight"], 1),
          "models_compared": stat["models"], "cheaper_models": stat["cheaper_models"],
          "listings": listing_counts[stat["city"]], "dealers": len(dealer_sets[stat["city"]])}
         for stat in city_stats.values()),
        key=lambda stat: stat["avg_diff_pct"],
    )

    return {
        "snapshot_date": str(snapshot)[:10],
        "priced_listings": len(priced),
        "total_listings": len(seen),
        "thresholds": {"min_listings": MIN_GROUP_LISTINGS, "min_dealers": MIN_GROUP_DEALERS,
                       "min_country_listings": MIN_CITY_LISTINGS},
        "cities": cities,
        "deals": deals,
    }


def get(force: bool = False) -> dict:
    snapshot = _latest_snapshot()
    with _lock:
        if not force and _memo.get("snapshot_date") == (str(snapshot)[:10] if snapshot else None) and _memo:
            return _memo
        path = _cache_path()
        if not force and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("snapshot_date") == (str(snapshot)[:10] if snapshot else None):
                    _memo.clear(); _memo.update(data)
                    return _memo
            except (OSError, ValueError):
                pass
        data = build(snapshot)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            logger.warning("Regional deals cache could not be written to %s", path)
        _memo.clear(); _memo.update(data)
        return _memo


def overview() -> dict:
    """İl bazlı karşılaştırma tablosunun tamamı (ilçe kırılımı yok)."""
    data = get()
    return {
        "snapshot_date": data.get("snapshot_date"),
        "thresholds": data.get("thresholds"),
        "priced_listings": data.get("priced_listings"),
        "cities": data.get("cities", []),
        "deals": data.get("deals", []),
    }
