"""AutoSense'in tek merkezî araç fiyat tahmin motoru.

Backend API ve bağımsız toplu tarama aynı ``estimate_price`` fonksiyonunu
kullanır. Tahmin tamamen paket referans fiyatlarına (baseline) dayanır --
AI/model tabanlı tahmin kullanılmıyor.
"""

from __future__ import annotations

import threading
from typing import Any, Iterable

from . import baseline_estimator as baseline
from . import market_estimator as liste_market
from django.conf import settings
from pathlib import Path


_lock = threading.RLock()
_baseline_cache: dict | None = None
_baseline_cache_mtime: float | None = None


def _db_mtime() -> float | None:
    try:
        return Path(settings.B2C_BASELINE_DB).stat().st_mtime
    except OSError:
        return None


def _text(value: Any, default: str = "bilinmiyor") -> str:
    result = "" if value is None else str(value).strip()
    return result or default


def _truthy(value: Any) -> bool:
    return value if isinstance(value, bool) else _text(value, "").lower() in {"1", "true", "evet", "var", "yes"}


def _model_name(engine: str, package: str | None) -> str:
    engine, package = _text(engine, ""), _text(package, "")
    return engine if not package or package.lower() in engine.lower() else f"{engine} {package}".strip()


def _load_baseline() -> dict:
    """paket_fiyatlari.db'yi bellege cache'ler. 2026-08-14 (GPT/Codex
    incelemesi): eskiden cache suresiz tutulurdu -- scraper/export_to_json.py
    DB'yi guncelledikten sonra, uzun yasayan Django worker/Celery process'leri
    reload_estimators() manuel cagrilmadan ya da process restart olmadan
    yeni fiyatlari HIC gormezdi. Artik her cagride DB dosyasinin mtime'ina
    bakilir -- dosya degismisse cache otomatik yenilenir. mtime kontrolu
    bir dosya sistemi stat() cagrisi kadar ucuz oldugu icin (gercek JSON
    parse/DB okuma degil) performans maliyeti ihmal edilebilir."""
    global _baseline_cache, _baseline_cache_mtime
    with _lock:
        current_mtime = _db_mtime()
        if _baseline_cache is None or current_mtime != _baseline_cache_mtime:
            _baseline_cache = baseline.load_paket_baseline()
            _baseline_cache_mtime = current_mtime
        return _baseline_cache


def reload_estimators() -> None:
    global _baseline_cache, _baseline_cache_mtime
    with _lock:
        _baseline_cache = None
        _baseline_cache_mtime = None
    liste_market.reload()


# Son 30 gunun liste ilanlarindan emsal harmanlama ayarlari -- bkz.
# market_estimator.py. Agirlik emsal sayisiyla artar: n/(n+K), en fazla MAX.
LISTE_WEIGHT_K = 8
LISTE_WEIGHT_MAX = 0.60
LISTE_ONLY_MIN_SAMPLES = 8      # paket referansi yoksa tek basina kullanmak icin


def _liste(category, brand, series, engine, package, year, km, damage, heavy) -> dict | None:
    try:
        dmg = list(damage) + ([{"parca": "Genel", "durum": "Ağır Hasarlı"}] if heavy else [])
        return liste_market.market_estimate(
            category=category, brand=brand, series=series, engine=engine,
            package=package, year=year, km=km, damage=dmg,
        )
    except Exception as exc:  # emsal bileseni asla tahmini bozmamali
        print(f"[central_price_estimator] liste emsal hatasi: {exc}")
        return None


def _predict_baseline(category, brand, series, engine, package, year, km, damage, heavy, gear, min_samples=None) -> dict[str, Any]:
    damage = list(damage)
    if heavy:
        damage.append({"parca": "Genel", "durum": "Ağır Hasarlı"})
    candidates = [_model_name(engine, package)] + ([package, engine] if package else [])
    entry = None
    for candidate in candidates:
        if candidate:
            entry = baseline.lookup_paket(_load_baseline(), brand, series, candidate, year, category=category, min_samples=min_samples)
        if entry is not None:
            break
    if entry is None:
        return {"found": False, "level": None, "base_price": None, "base_km": None, "base_count": 0, "km_factor": 1.0, "damage_factor": 1.0, "gear_factor": 1.0, "tahmini_fiyat": None, "year_fallback": None, "matched_key": None}
    return baseline.estimate_from_paket(entry, year, km, damage, gear=gear)


def estimate_price(
    category: str, brand: str, series: str, engine: str, package: str | None,
    year: int, km: float, damage: list[dict] | None = None,
    agir_hasar: bool = False, gear: str | None = None, *,
    fuel: str | None = None, city: str | None = None,
    seller_type: str | None = None, body_type: str | None = None,
    engine_cc: float | int | None = None, engine_hp: float | int | None = None,
    damage_known: bool = True, min_samples: int | None = None,
) -> dict[str, Any]:
    """Herkesin kullandığı kanonik tahmin sözleşmesi."""
    damage, heavy = list(damage or []), _truthy(agir_hasar)
    brand, series = _text(brand), _text(series)
    base = _predict_baseline(category, brand, series, engine, package, int(year), float(km), damage, heavy, gear, min_samples=min_samples)
    base_price = base.get("tahmini_fiyat") if base.get("found") else None

    if base_price:
        # 2026-08-15: Tahmin motorunun piyasaya kıyasla sistematik olarak
        # ~%5 YÜKSEK çıktığı gözlemlendi (kullanıcı geri bildirimi) --
        # kalıcı bir düzeltme olarak baseline sonucu burada %5 düşürülmüştü
        # (PRICE_BIAS_CORRECTION=0.95). Aynı anda baseline_estimator.py
        # tarafında bağımsız eklenmiş GLOBAL_CALIBRATION_FACTOR=1.10 (zıt
        # yönlü, %10 yukarı) ile zincirleme uygulanıyordu -- net ~%4.5
        # yukarı sapmaya yol açıyordu, fark edilmeden.
        #
        # 2026-08-24: search_soldvehiclerecord (59.006 gerçek satış kaydı)
        # üzerinde ölçüldü -- tek küresel sabit YANLIŞ VARSAYIMdı, marka
        # bazlı sapma %-0.5 (chery) ile %+27.5 (tofaş) arasında değişiyor
        # (bkz. Arabam Otomasyon/calibration_result.json, measure_
        # calibration_full.py -- tam metodoloji ve ham veri orada). Sabit
        # 0.95 kaldırıldı; kalibrasyon artık TEK noktada, baseline_
        # estimator.estimate_from_paket() içinde marka/kategori bazlı
        # ölçülmüş CALIBRATION_FACTORS tablosuyla uygulanıyor (base
        # sözlüğünde zaten "tahmini_fiyat" alanına işlenmiş halde gelir --
        # burada AYRICA bir düzeltme uygulanmaz, çünkü çift sayım olurdu).
        selected, source = int(round(base_price)), "baseline"
        confidence, reason = min(72, 55 + int(base.get("base_count", 0)) * 3), None
    else:
        selected, source, confidence, reason = None, "unavailable", 0, "Paket referansı bulunamadı."

    interval = 0.18
    mkt = _liste(category, brand, series, engine, package, int(year), float(km), damage, heavy)
    liste_weight = 0.0
    if mkt and selected:
        n = mkt["count"]
        liste_weight = min(LISTE_WEIGHT_MAX, n / (n + LISTE_WEIGHT_K))
        selected = int(round(((1 - liste_weight) * selected + liste_weight * mkt["value"]) / 1000) * 1000)
        source = "baseline+liste"
        confidence = min(82, confidence + min(10, n // 3))
    elif mkt and not selected and mkt["count"] >= LISTE_ONLY_MIN_SAMPLES:
        liste_weight = 1.0
        selected, source = mkt["value"], "liste"
        confidence = min(55, 30 + mkt["count"])
        interval = 0.22
        reason = (f"Paket referansı yok; son {liste_market.WINDOW_DAYS} günün "
                  f"{mkt['count']} emsal ilanından hesaplandı.")
    low = int(round(selected * (1 - interval) / 1000) * 1000) if selected else None
    high = int(round(selected * (1 + interval) / 1000) * 1000) if selected else None
    selected_version = {
        "baseline": "baseline-package-v1",
        "baseline+liste": "baseline-liste-v1",
        "liste": "liste-v1",
    }.get(source, "unavailable")

    result = dict(base)
    result.update({
        "found": selected is not None, "tahmini_fiyat": selected,
        "estimated_low": low, "estimated_high": high,
        "confidence_pct": int(confidence), "estimator_engine": source,
        "model_version": selected_version,
        "fallback_reason": reason, "ai_prediction": None,
        "baseline_prediction": int(base_price) if base_price else None,
        "ai_known_model_count": 0,
        "market_prediction": mkt["value"] if mkt else None,
        "market_count": mkt["count"] if mkt else 0,
        "market_weight": round(liste_weight, 3),
        "market_period": [mkt["period_start"], mkt["period_end"]] if mkt else None,
        "input_echo": {"category": category, "brand": brand, "series": series, "engine": engine, "package": package, "year": int(year), "km": float(km), "gear": gear},
    })
    return result


def estimate_many(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [estimate_price(**item) for item in items]
