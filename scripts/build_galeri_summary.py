#!/usr/bin/env python3
"""galeri.db (1.8 GB, 1.6M satır) -> fiyat hesaplama için küçük özet JSON.

Üretir:
  data/galeri_summary.json         (marka, seri, yıl) bazlı istatistikler — tüm tarih aralığı
  data/galeri_latest_snapshot.json en son güne ait canlı ilanlar (benzer ilan kartı için)

Kullanım:
  python3 scripts/build_galeri_summary.py data/galeri_export/galeri_latest.db
"""
import json
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_FILES = [
    ROOT / "backend/search/data/arabam_brands.json",
    ROOT / "backend/search/data/arabam_brands_ticari.json",
]
MIN_REAL_PRICE = 50_000
MAX_REAL_PRICE = 25_000_000
MIN_GROUP_SAMPLE = 3          # bu adetin altındaki (marka,seri,yıl) grupları JSON'a girmez
TREND_WEEKS = 26              # fiyat trendi için kaç haftalık geçmiş tutulsun

TR_LOWER = str.maketrans("IİŞĞÜÖÇ", "ıişğüöç")


def norm(v) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip()).translate(TR_LOWER).lower()


def parse_km(raw) -> float | None:
    digits = re.sub(r"[^\d]", "", str(raw or ""))
    return float(digits) if digits else None


def load_catalog() -> list[tuple[str, str, re.Pattern]]:
    """[(marka, seri, o modeli tanıyan regex)] listesi. En uzun seri adından en kısaya
    sıralanır ki "Egea Cross" once "Egea"den once denensin (daha spesifik eşleşme kazansın)."""
    pairs = []
    for f in CATALOG_FILES:
        if not f.exists():
            continue
        for brand in json.loads(f.read_text(encoding="utf-8")):
            bname = brand.get("name") or ""
            for series in brand.get("series") or []:
                sname = series.get("name") or ""
                if not bname or not sname:
                    continue
                pat = re.compile(re.escape(norm(bname)) + r".*" + re.escape(norm(sname)))
                pairs.append((bname, sname, pat, len(sname)))
    pairs.sort(key=lambda p: -p[3])
    return [(b, s, p) for b, s, p, _ in pairs]


def match_model(model_norm: str, catalog) -> tuple[str, str] | None:
    for brand, series, pat in catalog:
        if pat.search(model_norm):
            return brand, series
    return None


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/galeri_export/galeri_latest.db"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    print("Katalog yükleniyor...")
    catalog = load_catalog()
    print(f"  {len(catalog)} (marka, seri) çifti")

    print("Benzersiz modeller eşleştiriliyor...")
    model_rows = conn.execute("SELECT DISTINCT model FROM gallery_listings WHERE model IS NOT NULL").fetchall()
    model_map: dict[str, tuple[str, str] | None] = {}
    unmatched = 0
    for (model,) in model_rows:
        m = match_model(norm(model), catalog)
        model_map[model] = m
        if m is None:
            unmatched += 1
    print(f"  {len(model_map)} model, {unmatched} eşleşmedi (fiyat özetine girmeyecek)")

    print("Şehir bilgisi (galleries) yükleniyor...")
    gallery_city = {}
    for row in conn.execute("SELECT gallery_name, city, district FROM galleries"):
        gallery_city[row["gallery_name"]] = (row["city"] or "", row["district"] or "")

    print("Tüm satırlar okunuyor (bu birkaç dakika sürebilir)...")
    groups = defaultdict(lambda: {
        "prices": [], "colors": defaultdict(list), "cities": defaultdict(list),
        "weekly": defaultdict(list), "listing_keys": set(), "galleries": set(),
        "latest_date": None,
    })
    total = 0
    latest_overall = None
    cur = conn.execute(
        "SELECT gallery_name, snapshot_date, listing_key, model, year_raw, color, price FROM gallery_listings"
    )
    for row in cur:
        total += 1
        if total % 500_000 == 0:
            print(f"  {total:,} satır işlendi...")
        price = row["price"]
        if price is None or not (MIN_REAL_PRICE <= price <= MAX_REAL_PRICE):
            continue
        m = model_map.get(row["model"])
        if m is None:
            continue
        try:
            year = int(str(row["year_raw"]).strip())
        except (TypeError, ValueError):
            continue
        if not 1950 <= year <= 2100:
            continue
        brand, series = m
        key = (brand, series, year)
        g = groups[key]
        g["prices"].append(price)
        g["listing_keys"].add(row["listing_key"])
        g["galleries"].add(row["gallery_name"])
        if row["color"]:
            g["colors"][norm(row["color"])].append(price)
        city, district = gallery_city.get(row["gallery_name"], ("", ""))
        if city:
            g["cities"][norm(city)].append(price)
        snap = row["snapshot_date"]
        if snap:
            if g["latest_date"] is None or snap > g["latest_date"]:
                g["latest_date"] = snap
            if latest_overall is None or snap > latest_overall:
                latest_overall = snap
            try:
                week = datetime.strptime(snap[:10], "%Y-%m-%d").strftime("%G-W%V")
                g["weekly"][week].append(price)
            except ValueError:
                pass

    print(f"Toplam {total:,} satır tarandı. {len(groups)} (marka,seri,yıl) grubu bulundu.")

    print("Özet JSON hazırlanıyor...")
    summary = {}
    dropped_small = 0
    for (brand, series, year), g in groups.items():
        if len(g["prices"]) < MIN_GROUP_SAMPLE:
            dropped_small += 1
            continue
        prices = sorted(g["prices"])
        median = statistics.median(prices)
        overall_avg = sum(prices) / len(prices)
        colors = {}
        for color, cp in g["colors"].items():
            if len(cp) >= 8 and len(prices) >= 20:
                colors[color] = {
                    "factor_pct": round((sum(cp) / len(cp) - overall_avg) / overall_avg * 100, 1),
                    "sample_count": len(cp),
                }
        cities = {}
        for city, cp in g["cities"].items():
            if len(cp) >= 5:
                cities[city] = {"avg_price": round(sum(cp) / len(cp)), "count": len(cp)}
        weekly_sorted = sorted(g["weekly"].items())[-TREND_WEEKS:]
        trend = [
            {"week": w, "avg_price": round(sum(wp) / len(wp)), "count": len(wp)}
            for w, wp in weekly_sorted if len(wp) >= MIN_GROUP_SAMPLE
        ]
        key_str = f"{brand}|{series}|{year}"
        summary[key_str] = {
            "brand": brand, "series": series, "year": year,
            "sample_count": len(prices),
            "unique_vehicles": len(g["listing_keys"]),
            "unique_sellers": len(g["galleries"]),
            "median_price": round(median),
            "p25": round(prices[len(prices) // 4]),
            "p75": round(prices[len(prices) * 3 // 4]),
            "latest_date": g["latest_date"],
            "colors": colors,
            "cities": cities,
            "price_trend": trend,
        }

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_db": str(db_path.name),
        "source_row_count": total,
        "source_date_range": [
            conn.execute("SELECT MIN(snapshot_date) FROM gallery_listings").fetchone()[0],
            latest_overall,
        ],
        "unmatched_models": unmatched,
        "dropped_small_groups": dropped_small,
        "group_count": len(summary),
        "groups": summary,
    }
    out_path = ROOT / "data/galeri_summary.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Yazıldı: {out_path} ({out_path.stat().st_size / 1e6:.1f} MB), {len(summary)} grup")

    print("Son güne ait canlı ilanlar çıkarılıyor (benzer ilan kartı için)...")
    latest_rows = []
    cur = conn.execute(
        """
        SELECT gl.gallery_name, gl.model, gl.title, gl.year_raw, gl.km_raw, gl.color,
               gl.price, gl.post_url, gl.post_age_days
          FROM gallery_listings gl
         WHERE gl.snapshot_date = ? AND gl.price BETWEEN ? AND ?
        """,
        (latest_overall, MIN_REAL_PRICE, MAX_REAL_PRICE),
    )
    for row in cur:
        m = model_map.get(row["model"])
        if m is None:
            continue
        try:
            year = int(str(row["year_raw"]).strip())
        except (TypeError, ValueError):
            continue
        city, district = gallery_city.get(row["gallery_name"], ("", ""))
        latest_rows.append({
            "brand": m[0], "series": m[1], "year": year,
            "title": (row["title"] or row["model"] or "").strip(),
            "km": parse_km(row["km_raw"]),
            "color": (row["color"] or "").strip() or None,
            "price": int(row["price"]),
            "url": row["post_url"] or None,
            "city": city or None, "district": district or None,
            "gallery": row["gallery_name"],
            "post_age_days": row["post_age_days"],
        })
    snap_path = ROOT / "data/galeri_latest_snapshot.json"
    snap_path.write_text(
        json.dumps({"snapshot_date": latest_overall, "listings": latest_rows}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Yazıldı: {snap_path} ({snap_path.stat().st_size / 1e6:.1f} MB), {len(latest_rows)} ilan")
    print("\nBİTTİ.")


if __name__ == "__main__":
    main()
