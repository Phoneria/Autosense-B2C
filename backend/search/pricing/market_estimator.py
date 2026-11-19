"""Güncel piyasa bileşeni: son 30 günün arabam.com liste ilanlarından tahmin.

Kaynak, B2B tarafının her akşam 20:00'de topladığı `liste_ilanlari` tablosu
(Galeri/liste_ilanlari_scraper.py -> galeri_latest.db). Bu dosyanın bir
kopyası B2C sunucusuna `data/liste_ilanlari.db` olarak konur
(bkz. settings.B2C_LISTE_DB). Dosya yoksa ya da veri yetersizse bu modül
None döner ve tahmin eskisi gibi sadece paket referansından yapılır.

Yöntem (deterministik, model yok):
  1. Aynı marka + seri + motor (+ paket verildiyse aynı paket) ilanları alınır.
  2. Hedef yıla ±1 (yetmezse ±2) yıl penceresi uygulanır, km'si bilinmeyen
     ilanlar kullanılmaz (km fiyatın en büyük belirleyicilerinden).
  3. Her ilanın fiyatı, paket motorunun AYNI yaş ve km eğrileriyle hedef
     araca uyarlanır (bkz. baseline_estimator._age_adjustment_factor /
     km_factor) -- iki bileşen birbiriyle tutarlı kalsın diye.
  4. Uç değerler budanır, medyan alınır; hasar ve marka kalibrasyonu
     (ilan fiyatı -> gerçek satış fiyatı) paket tahminiyle aynı şekilde
     uygulanır.
"""

from __future__ import annotations

import re
import statistics
import threading
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings

from . import baseline_estimator as baseline

WINDOW_DAYS = 30
MIN_MARKET_SAMPLES = 5          # bu kadar emsal ilan yoksa piyasa bileşeni kullanılmaz
MIN_REAL_PRICE = 50_000
MAX_REAL_PRICE = 200_000_000
OUTLIER_LOW, OUTLIER_HIGH = 0.60, 1.60   # medyana göre budama sınırları

_lock = threading.RLock()
_cache: dict = {"key": None, "index": {}, "period": None}

_TR_MAP = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
                         "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})


def _norm(value) -> str:
    text = str(value or "").translate(_TR_MAP).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def _int(value) -> int | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _db_path() -> Path:
    return Path(getattr(settings, "B2C_LISTE_DB", ""))


def _file_key():
    try:
        st = _db_path().stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def data_version() -> str:
    key = _file_key()
    return f"{key[0]}" if key else "0"


def _load_rows() -> list[dict]:
    from .reference import readonly_connection

    conn = readonly_connection(_db_path())
    try:
        son = conn.execute("SELECT MAX(snapshot_date) FROM liste_ilanlari").fetchone()[0]
        if not son:
            return []
        bas = (date.fromisoformat(son) - timedelta(days=WINDOW_DAYS - 1)).isoformat()
        # Aynı ilan birden çok gün görünebilir; en güncel fiyatı kullan.
        rows = conn.execute(
            """
            SELECT l.listing_key, l.snapshot_date, l.model, l.year_raw, l.km_raw, l.price
            FROM liste_ilanlari l
            JOIN (SELECT listing_key, MAX(snapshot_date) AS d FROM liste_ilanlari
                  WHERE snapshot_date >= ? GROUP BY listing_key) s
              ON s.listing_key = l.listing_key AND s.d = l.snapshot_date
            """,
            (bas,),
        ).fetchall()
        return [dict(r) | {"_period": (bas, son)} for r in rows]
    finally:
        conn.close()


def _build_index() -> tuple[dict, tuple | None]:
    from ..services.price_estimator import parse_listing_identity

    rows = _load_rows()
    period = rows[0]["_period"] if rows else None
    identity_cache: dict[str, dict] = {}
    index: dict[tuple, list[tuple]] = {}
    for r in rows:
        price, year, km = _int(r["price"]), _int(r["year_raw"]), _int(r["km_raw"])
        if not price or not year or km is None:
            continue
        if not (MIN_REAL_PRICE <= price <= MAX_REAL_PRICE) or not (1950 <= year <= 2100):
            continue
        model = str(r["model"] or "").strip()
        if not model:
            continue
        ident = identity_cache.get(model)
        if ident is None:
            ident = identity_cache[model] = parse_listing_identity(model)
        key = (_norm(ident.get("brand")), _norm(ident.get("series")), _norm(ident.get("engine")))
        index.setdefault(key, []).append((_norm(ident.get("package")), year, km, price))
    return index, period


def _get_index() -> tuple[dict, tuple | None]:
    key = _file_key()
    if key is None:
        return {}, None
    with _lock:
        if _cache["key"] != key:
            try:
                _cache["index"], _cache["period"] = _build_index()
            except Exception as exc:  # bozuk/eksik dosya tahmini durdurmasın
                print(f"[market_estimator] liste verisi okunamadı: {exc}")
                _cache["index"], _cache["period"] = {}, None
            _cache["key"] = key
        return _cache["index"], _cache["period"]


def reload() -> None:
    with _lock:
        _cache["key"] = None


def _package_matches(row_pkg: str, target_pkg: str) -> bool:
    # Sadece birebir eşleşme: "Urban" ile "Urban Plus" farklı paketlerdir.
    return bool(row_pkg) and row_pkg == target_pkg


def market_estimate(*, category: str, brand: str, series: str, engine: str,
                    package: str | None, year: int, km: float,
                    damage: list[dict] | None = None) -> dict | None:
    """Son 30 günün emsal ilanlarından piyasa tahmini. Yetersizse None."""
    index, period = _get_index()
    if not index:
        return None
    rows = index.get((_norm(brand), _norm(series), _norm(engine)), [])
    if package:
        target_pkg = _norm(package)
        rows = [r for r in rows if _package_matches(r[0], target_pkg)]
    if not rows:
        return None

    year, km = int(year), float(km)
    chosen, tolerance = [], 0
    for tolerance in (1, 2):
        chosen = [r for r in rows if abs(r[1] - year) <= tolerance]
        if len(chosen) >= MIN_MARKET_SAMPLES:
            break
    if len(chosen) < MIN_MARKET_SAMPLES:
        return None

    adjusted = [
        price
        * baseline._age_adjustment_factor(row_year - year)
        * baseline.km_factor(km, row_km if row_km > 0 else 1)
        for _, row_year, row_km, price in chosen
    ]
    mid = statistics.median(adjusted)
    trimmed = [p for p in adjusted if OUTLIER_LOW * mid <= p <= OUTLIER_HIGH * mid]
    if len(trimmed) < MIN_MARKET_SAMPLES:
        return None
    value = statistics.median(trimmed)

    df = baseline.damage_factor(list(damage or []), value)
    calib = baseline._calibration_factor(baseline._slugify(brand), category)
    estimate = value * df * calib

    return {
        "value": int(round(estimate, -3)),
        "count": len(trimmed),
        "year_tolerance": tolerance,
        "package_level": bool(package),
        "period_start": period[0] if period else None,
        "period_end": period[1] if period else None,
        "damage_factor": df,
        "calibration_factor": calib,
    }
