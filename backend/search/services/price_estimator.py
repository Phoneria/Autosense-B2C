"""Django adapter for AutoSense's single central price estimator."""

from __future__ import annotations

from functools import lru_cache
import re

from ..pricing.central_price_estimator import (
    estimate_many as _estimate_many,
    estimate_price as _estimate_price,
    reload_estimators,
)
from .arabam_vehicles_service import load_arabam_vehicles


def reload_dbs() -> None:
    """Reload package-price references."""
    reload_estimators()


def estimate(
    category: str,
    brand: str,
    series: str,
    engine: str,
    package: str | None,
    year: int,
    km: float,
    damage: list[dict] | None = None,
    agir_hasar: bool = False,
    gear: str | None = None,
    **extra,
) -> dict:
    return _estimate_price(
        category=category,
        brand=brand,
        series=series,
        engine=engine,
        package=package,
        year=year,
        km=km,
        damage=damage,
        agir_hasar=agir_hasar,
        gear=gear,
        **extra,
    )


def estimate_batch(items: list[dict]) -> list[dict]:
    return _estimate_many(items)


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


@lru_cache(maxsize=1)
def _vehicle_catalog() -> tuple[dict, ...]:
    return tuple(load_arabam_vehicles())


def parse_listing_identity(full_model: str) -> dict:
    """Best-effort split of 'Brand Series Engine Package' gallery strings."""
    raw = re.sub(r"\s+", " ", str(full_model or "").strip())
    normalized = _norm(raw)
    best = None
    for brand in _vehicle_catalog():
        name = str(brand.get("name") or "").strip()
        n = _norm(name)
        if normalized == n or normalized.startswith(n + " "):
            if best is None or len(n) > len(best[0]):
                best = (n, name, brand)
    if best is None:
        parts = raw.split(" ", 1)
        return {"category": "otomobil", "brand": parts[0] if parts else "", "series": "bilinmiyor", "engine": parts[1] if len(parts) > 1 else "bilinmiyor", "package": None}

    _, brand_name, brand_data = best
    remainder = raw[len(brand_name):].strip()
    remainder_norm = _norm(remainder)
    series_match = None
    for series in brand_data.get("series") or []:
        name = str(series.get("name") or "").strip()
        n = _norm(name)
        if remainder_norm == n or remainder_norm.startswith(n + " "):
            if series_match is None or len(n) > len(series_match[0]):
                series_match = (n, name, series)
    if series_match is None:
        parts = remainder.split(" ", 1)
        return {"category": brand_data.get("category", "otomobil"), "brand": brand_name, "series": parts[0] if parts else "bilinmiyor", "engine": parts[1] if len(parts) > 1 else "bilinmiyor", "package": None}

    _, series_name, series_data = series_match
    tail = remainder[len(series_name):].strip()
    tail_norm = _norm(tail)
    engine_match = None
    for engine in series_data.get("engines") or []:
        name = str(engine.get("name") or "").strip()
        n = _norm(name)
        if tail_norm == n or tail_norm.startswith(n + " "):
            if engine_match is None or len(n) > len(engine_match[0]):
                engine_match = (n, name, engine)
    if engine_match is None:
        return {"category": brand_data.get("category", "otomobil"), "brand": brand_name, "series": series_name, "engine": tail or "bilinmiyor", "package": None}

    _, engine_name, engine_data = engine_match
    package = tail[len(engine_name):].strip() or None
    return {"category": brand_data.get("category", "otomobil"), "brand": brand_name, "series": series_name, "engine": engine_name, "package": package}


def estimate_listing(full_model: str, year: int, km: float, **extra) -> dict:
    identity = parse_listing_identity(full_model)
    return estimate(year=year, km=km, damage=[], agir_hasar=False, gear=None, **identity, **extra)
