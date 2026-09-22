"""Araç Rehberi: model bazında talep, stok, satış süresi ve fiyat trendi.

Kaynak galeri.db'deki günlük galeri snapshot'larıdır. Gerçek satış verisi yok;
"satıldı (tahmini)" = ilanın yayından kalkması. Bir ilanın kalktığını söylemek
için galerinin sonraki en az iki snapshot'ta hâlâ taranmış olması gerekir
(tarama boşluğu satış sayılmasın), son iki snapshot'ta görülen ilanlar için
karar verilmez.

Fiyat trendi ham ortalama DEĞİLDİR: her ilan AutoSense ile bir kez fiyatlanır,
haftalık "ilan fiyatı / piyasa değeri" medyanı izlenir. Böylece o hafta daha
eski ya da yüksek km'li araç gelmesi fiyat düşmüş gibi görünmez.

Hesap ağırdır (~1 dk); sonuç snapshot tarihine göre dosyaya yazılır, yeni
snapshot geldiğinde eski sonuç sunulurken arka planda yeniden hesaplanır.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median

from django.conf import settings

from .b2c import _MAX_REAL_PRICE, _MIN_REAL_PRICE
from .price_estimator import estimate, parse_listing_identity
from .vehicle_traits import normalize as traits_norm

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30
MIN_WEEK_SAMPLES = 8
MIN_ACTIVE_FOR_LISTS = 20
MIN_REMOVED_FOR_SPEED = 15

_lock = threading.Lock()
_building = threading.Event()
_memo: dict = {}


def _cache_path() -> Path:
    return Path(getattr(settings, "B2C_GUIDE_CACHE", settings.PROJECT_DIR / ".local/vehicle_guide.json"))


def _gallery_conn() -> sqlite3.Connection:
    return sqlite3.connect(Path(settings.B2C_GALLERY_DB).resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False)


def _latest_snapshot() -> str | None:
    try:
        conn = _gallery_conn()
        try:
            return conn.execute("SELECT MAX(snapshot_date) FROM gallery_listings").fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return None


def _int(raw) -> int | None:
    digits = re.sub(r"\D", "", str(raw or ""))
    return int(digits) if digits else None


def _week(d: str) -> str:
    day = date.fromisoformat(d[:10])
    return (day - timedelta(days=day.weekday())).isoformat()


def _slug(text: str) -> str:
    return re.sub(r"\s+", "-", traits_norm(text))


def _trait_engines() -> dict[tuple[str, str], list[dict]]:
    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    try:
        conn = sqlite3.connect(Path(settings.B2C_TRAITS_DB).resolve().as_uri() + "?mode=ro", uri=True)
        for key, marka, seri, etiket, ilan, k, i, kt in conn.execute(
                "SELECT anahtar, marka, seri, etiket, ilan_sayisi, kronik_n, iyi_n, kotu_n FROM vehicles ORDER BY ilan_sayisi DESC"):
            out[(traits_norm(marka), traits_norm(seri))].append(
                {"key": key, "label": etiket, "listings": ilan, "kronik": k, "iyi": i, "kotu": kt})
        conn.close()
    except Exception:
        pass
    return out


def build(snapshot: str | None = None) -> dict:
    conn = _gallery_conn()
    try:
        snapshot = snapshot or conn.execute("SELECT MAX(snapshot_date) FROM gallery_listings").fetchone()[0]
        if not snapshot:
            return {"snapshot_date": None, "models": {}, "home": {}}
        dates = [r[0] for r in conn.execute("SELECT DISTINCT snapshot_date FROM gallery_listings WHERE snapshot_date <= ? ORDER BY 1", (snapshot,))]
        date_index = {d: i for i, d in enumerate(dates)}
        gallery_dates: dict[str, list[int]] = defaultdict(list)
        for gallery, d in conn.execute("SELECT DISTINCT gallery_name, snapshot_date FROM gallery_listings WHERE snapshot_date <= ?", (snapshot,)):
            gallery_dates[gallery].append(date_index[d])
        for v in gallery_dates.values():
            v.sort()

        listings: dict[str, dict] = {}
        stock: dict[tuple[str, int], int] = defaultdict(int)
        identity_cache: dict[str, dict] = {}
        weekly_seen: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
        for key, gallery, model, d, year_raw, km_raw, price, age in conn.execute(
                """SELECT listing_key, gallery_name, model, snapshot_date, year_raw, km_raw, price, post_age_days
                     FROM gallery_listings WHERE snapshot_date <= ? AND price BETWEEN ? AND ? ORDER BY snapshot_date""",
                (snapshot, _MIN_REAL_PRICE, _MAX_REAL_PRICE)):
            if not model:
                continue
            ident = identity_cache.get(model)
            if ident is None:
                ident = parse_listing_identity(model)
                identity_cache[model] = ident
            if not ident.get("series") or ident["series"] == "bilinmiyor":
                continue
            mkey = _slug(f"{ident['brand']} {ident['series']}")
            idx = date_index[d]
            item = listings.get(key)
            if item is None:
                item = listings[key] = {"m": mkey, "g": gallery, "raw": model, "first": idx, "last": idx,
                                        "year": _int(year_raw), "km": _int(km_raw), "age": age, "price": int(price)}
            else:
                item["last"] = idx
                item["price"] = int(price)
                if age is not None:
                    item["age"] = age
            stock[(mkey, idx)] += 1
            weekly_seen[(mkey, _week(d))][key] = int(price)

        meta: dict[str, dict] = {}
        for ident in identity_cache.values():
            if ident.get("series") and ident["series"] != "bilinmiyor":
                mkey = _slug(f"{ident['brand']} {ident['series']}")
                meta.setdefault(mkey, {"name": f"{ident['brand']} {ident['series']}", "brand": ident["brand"],
                                       "series": ident["series"], "category": ident["category"]})

        estimates: dict[tuple, float | None] = {}
        ratios: dict[str, float] = {}
        for key, item in listings.items():
            if not item["year"] or item["km"] is None:
                continue
            ident = identity_cache[item["raw"]]
            ck = (item["raw"], item["year"], item["km"] // 5000)
            if ck not in estimates:
                try:
                    r = estimate(year=item["year"], km=item["km"], damage=[], agir_hasar=False, gear=None, **ident)
                    estimates[ck] = r.get("tahmini_fiyat") if r.get("found") else None
                except Exception:
                    estimates[ck] = None
            value = estimates[ck]
            if value:
                ratio = item["price"] / value
                if 0.5 <= ratio <= 1.8:
                    ratios[key] = value

        last = len(dates) - 1
        window_start = date.fromisoformat(snapshot) - timedelta(days=WINDOW_DAYS)
        per_model = defaultdict(lambda: {"removed": [], "new": 0, "active": 0, "dealers": set(), "prices": [],
                                         "removed_w": defaultdict(int), "new_w": defaultdict(int)})
        for key, item in listings.items():
            pm = per_model[item["m"]]
            first_day, last_day = dates[item["first"]], dates[item["last"]]
            if item["last"] == last:
                pm["active"] += 1
                pm["dealers"].add(item["g"])
                pm["prices"].append(item["price"])
            if item["first"] > 0 and gallery_dates[item["g"]][0] < item["first"]:
                pm["new_w"][_week(first_day)] += 1
                if date.fromisoformat(first_day) >= window_start:
                    pm["new"] += 1
            if item["last"] <= last - 2:
                later = [i for i in gallery_dates[item["g"]] if i > item["last"]]
                if len(later) >= 2:
                    days = (date.fromisoformat(last_day) - date.fromisoformat(first_day)).days
                    on_market = max(days, item["age"] or 0)
                    pm["removed"].append((last_day, on_market))
                    pm["removed_w"][_week(last_day)] += 1

        weeks = sorted({_week(d) for d in dates})
        trait_map = _trait_engines()
        models = {}
        for mkey, pm in per_model.items():
            if mkey not in meta or pm["active"] + len(pm["removed"]) < 10:
                continue
            removed_30 = [r for r in pm["removed"] if date.fromisoformat(r[0]) >= window_start]
            stock_w, price_w, index_w, samples_w = [], [], [], []
            base_ratio = None
            for w in weeks:
                idxs = [date_index[d] for d in dates if _week(d) == w]
                stock_w.append(round(sum(stock[(mkey, i)] for i in idxs) / len(idxs)) if idxs else 0)
                seen = weekly_seen.get((mkey, w), {})
                week_ratios = [p / ratios[k] for k, p in seen.items() if k in ratios]
                samples_w.append(len(seen))
                price_w.append(int(median(seen.values())) if len(seen) >= MIN_WEEK_SAMPLES else None)
                if len(week_ratios) >= MIN_WEEK_SAMPLES:
                    r = median(week_ratios)
                    base_ratio = base_ratio or r
                    index_w.append(round(r / base_ratio * 100, 1))
                else:
                    index_w.append(None)
            valid = [v for v in index_w[:-1] if v is not None]   # son hafta yarım olabilir
            change_4w = None
            if len(valid) >= 5:
                change_4w = round((valid[-1] / valid[-5] - 1) * 100, 1)
            engines = trait_map.get((traits_norm(meta[mkey]["brand"]), traits_norm(meta[mkey]["series"])), [])
            avg_stock = (sum(stock_w[-5:-1]) / 4) if len(stock_w) >= 5 else (sum(stock_w) / max(1, len(stock_w)))
            models[mkey] = {
                **meta[mkey], "key": mkey,
                "active": pm["active"], "dealers": len(pm["dealers"]),
                "median_price": int(median(pm["prices"])) if pm["prices"] else None,
                "removed_30d": len(removed_30), "new_30d": pm["new"],
                "turnover_pct": round(len(removed_30) / avg_stock * 100, 1) if avg_stock else None,
                "median_days_on_market": int(median(r[1] for r in removed_30)) if len(removed_30) >= 5 else None,
                "price_change_4w_pct": change_4w,
                "trait_engines": engines,
                # İlk hafta tarayıcı kapsamı oturmadan önceki döneme denk geliyor (yeni/kalkan
                # sayıları şişik), son haftanın kalkan ilanları henüz kesinleşmedi -> gösterilmez.
                "weekly": {"stock": stock_w,
                           "new": [None if i == 0 else pm["new_w"].get(w, 0) for i, w in enumerate(weeks)],
                           "removed": [None if i in (0, len(weeks) - 1) else pm["removed_w"].get(w, 0) for i, w in enumerate(weeks)],
                           "median_price": price_w, "price_index": index_w, "samples": samples_w},
            }
    finally:
        conn.close()

    def summary(m):
        return {k: m[k] for k in ("key", "name", "category", "active", "removed_30d", "median_price",
                                  "median_days_on_market", "price_change_4w_pct", "turnover_pct")}

    pool = [m for m in models.values() if m["active"] >= MIN_ACTIVE_FOR_LISTS]
    home = {
        "most_demand": [summary(m) for m in sorted(pool, key=lambda m: -m["removed_30d"])[:10]],
        "fastest": [summary(m) for m in sorted((m for m in pool if m["median_days_on_market"] is not None and m["removed_30d"] >= MIN_REMOVED_FOR_SPEED),
                                               key=lambda m: m["median_days_on_market"])[:10]],
        "rising": [summary(m) for m in sorted((m for m in pool if (m["price_change_4w_pct"] or 0) > 0), key=lambda m: -m["price_change_4w_pct"])[:8]],
        "falling": [summary(m) for m in sorted((m for m in pool if (m["price_change_4w_pct"] or 0) < 0), key=lambda m: m["price_change_4w_pct"])[:8]],
        "most_listed": [summary(m) for m in sorted(pool, key=lambda m: -m["active"])[:10]],
    }
    return {
        "snapshot_date": str(snapshot)[:10], "first_date": dates[0], "snapshot_count": len(dates),
        "window_days": WINDOW_DAYS, "weeks": weeks, "home": home, "models": models,
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }


def _save(data: dict) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Vehicle guide cache could not be written to %s", path)


def rebuild() -> dict:
    data = build()
    _save(data)
    with _lock:
        _memo.clear(); _memo.update(data)
    return data


def _background_rebuild() -> None:
    if _building.is_set():
        return
    _building.set()
    def run():
        try:
            rebuild()
        except Exception:
            logger.exception("Vehicle guide rebuild failed")
        finally:
            _building.clear()
    threading.Thread(target=run, daemon=True).start()


def get() -> dict:
    latest = _latest_snapshot()
    latest = str(latest)[:10] if latest else None
    with _lock:
        if not _memo:
            path = _cache_path()
            if path.exists():
                try:
                    _memo.update(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    _memo.clear()
        current = dict(_memo) if _memo else None
    if current is None:
        return rebuild()
    if current.get("snapshot_date") != latest:
        _background_rebuild()
    return current


def home(premium: bool) -> dict:
    data = get()
    index = sorted(({"key": m["key"], "name": m["name"], "category": m["category"], "active": m["active"],
                     "removed_30d": m["removed_30d"], "has_traits": bool(m["trait_engines"])}
                    for m in data["models"].values()), key=lambda m: -m["active"])
    return {"snapshot_date": data["snapshot_date"], "first_date": data["first_date"],
            "snapshot_count": data["snapshot_count"], "window_days": data["window_days"],
            "home": data["home"], "models": index, "premium": premium}


def model(key: str, premium: bool) -> dict | None:
    data = get()
    m = data["models"].get(key)
    if not m:
        return None
    out = {k: v for k, v in m.items() if k != "weekly"}
    out.update({"snapshot_date": data["snapshot_date"], "window_days": data["window_days"], "premium": premium})
    if premium:
        out.update({"weeks": data["weeks"], "weekly": m["weekly"]})
        same = [x for x in data["models"].values() if x["category"] == m["category"] and x["key"] != key and x["median_price"] and m["median_price"]]
        same.sort(key=lambda x: abs(x["median_price"] - m["median_price"]))
        out["similar"] = [{"key": x["key"], "name": x["name"], "median_price": x["median_price"], "active": x["active"],
                           "removed_30d": x["removed_30d"], "price_change_4w_pct": x["price_change_4w_pct"]} for x in same[:5]]
    return out


def compare(keys: list[str]) -> dict:
    data = get()
    found = [data["models"][k] for k in keys if k in data["models"]]
    return {"weeks": data["weeks"], "models": [{"key": m["key"], "name": m["name"], "weekly": m["weekly"],
            "median_price": m["median_price"], "removed_30d": m["removed_30d"], "active": m["active"],
            "median_days_on_market": m["median_days_on_market"], "price_change_4w_pct": m["price_change_4w_pct"]} for m in found]}
