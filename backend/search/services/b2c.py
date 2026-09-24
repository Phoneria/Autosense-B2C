"""B2C (son kullanıcı) tarafının servis katmanı.

B2C arayüzü (frontend/ — Vite + React) üç endpoint çağırır:

    GET  /api/b2c/locations          -> il / ilçe seçenekleri
    POST /api/b2c/vehicle-defaults   -> seçilen araç için vites vb. varsayılanlar
    POST /api/b2c/analyze            -> tek araç için tam analiz

Bu modül o üçünün iş mantığını tutar. Fiyat tahmini için B2B tarafıyla
AYNI merkezi motoru (services.price_estimator -> central_price_estimator)
kullanır — B2C'ye özel ikinci bir tahmin mantığı bilerek yazılmadı, yoksa
iki taraf zamanla birbirinden ayrışırdı.

Veri kaynakları:
  * Postgres `search_listing`         — analiz edilmiş arabam.com ilanları
  * data/galeri_summary.json          — galeri ilanlarının (marka,seri,yıl)
                                         bazında özetlenmiş istatistikleri
                                         (fiyat trendi + bölgesel sinyal + renk)
  * data/galeri_latest_snapshot.json  — en son güne ait canlı galeri ilanları
                                         (benzer ilan kartı)
  Bu iki JSON, scripts/build_galeri_summary.py ile üretilir (kaynak: galeri.db,
  artık production'da tutulmuyor).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import threading
import unicodedata
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any

from django.core.cache import cache
from django.db.models import Q

# All reference data is opened read-only, outside the account database.
from django.conf import settings
from ..pricing.reference import readonly_connection

from . import galeri_summary

_conn_local = threading.local()


def _galeri_conn():
    """`galeri.db`'ye tembel bağlantı. Fiyat analizi artık bunu KULLANMIYOR (bkz.
    galeri_summary.py); bu sadece galeri.db'nin hâlâ TAM veriye ihtiyaç duyan diğer
    özellikleri için var: regional.py (bölgesel fırsatlar, ilçe kırılımı) ve
    guide.py (Araç Rehberi, çoklu-snapshot analizi kendi bağlantısını açıyor)."""
    path = str(settings.B2C_GALLERY_DB)
    conn = getattr(_conn_local, "conn", None)
    if conn is None or getattr(_conn_local, "path", None) != path:
        if conn is not None:
            conn.close()
        conn = readonly_connection(path)
        _conn_local.conn = conn
        _conn_local.path = path
    return conn


# Kiralık araç / "fiyat sorunuz" ilanları galeri verisinde 1.000 TL gibi
# sahte fiyatlarla duruyor (bkz. gallery_listings örnekleri). Ortalamayı
# bozmasınlar diye taban eşik.
_MIN_REAL_PRICE = 50_000
_MAX_REAL_PRICE = 25_000_000

_TR_LOWER = str.maketrans("IİŞĞÜÖÇ", "ıişğüöç")


@lru_cache(maxsize=16384)
def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip()).translate(_TR_LOWER).lower()


def _tr_key(v: str) -> str:
    """Türkçe alfabetik sıralama için kaba anahtar."""
    order = "aâbcçdefgğhıijklmnoöprsştuüvyz"
    return "".join(
        chr(48 + order.index(ch)) if ch in order else ch for ch in _norm(v)
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1) İl / ilçe seçenekleri
# ═══════════════════════════════════════════════════════════════════════════

_LOCATIONS_CACHE_KEY = "b2c:locations:v3"
_LOCATIONS_TTL = 60 * 60 * 6


def _locations_from_galeri() -> dict[str, set[str]]:
    """galeri_latest_snapshot.json'daki ilanların city/district alanları
    (üretim script'inde `galleries` tablosundan JOIN edilmiş) — ana kaynak burası."""
    out: dict[str, set[str]] = {}
    for row in galeri_summary.latest_snapshot().get("listings", []):
        city = str(row.get("city") or "").strip()
        district = str(row.get("district") or "").strip()
        if not city:
            continue
        out.setdefault(city, set())
        if district:
            out[city].add(district)
    return out


def _split_address(address: str) -> tuple[str, str]:
    """`search_listing.address` arabam.com'un ham "konum" metnidir ve tek bir
    formata sahip değil. Gözlenen biçimler:

        "Kadıköy, İstanbul"
        "Bostancı Mah., Kadıköy, İstanbul"
        "İstanbul"

    Kural: son parça il, ondan önceki parça ilçe. Tek parça varsa sadece il.
    (Arabam Otomasyon/preprocess.standardize_location ile aynı mantık.)
    """
    parts = [p.strip() for p in str(address or "").split(",") if p.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[-1], parts[-2]


def _locations_from_listings() -> dict[str, set[str]]:
    """Postgres `search_listing.address` — galeri verisinde olmayan il/ilçeleri
    de yakalamak için ikinci kaynak."""
    from ..models import Listing

    out: dict[str, set[str]] = {}
    try:
        addresses = list(
            Listing.objects.exclude(address="")
            .values_list("address", flat=True)
            .distinct()[:200_000]
        )
    except Exception:
        # Referans DB okunamazsa (izin, eksik dosya) il listesi yine de
        # sabit Türkiye listesi + galeri verisiyle dönmeli.
        return out
    for address in addresses:
        city, district = _split_address(address)
        if not city or len(city) > 40:
            continue
        out.setdefault(city, set())
        if district and len(district) <= 40:
            out[city].add(district)
    return out


_TR_LOCATIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tr_il_ilce.json")


def _loc_key(v: str) -> str:
    """İl/ilçe eşleştirme anahtarı: büyük/küçük harf ve Türkçe karakter farkı
    (İstanbul/Istanbul/ISTANBUL, Çan/Can) aynı kayda düşer."""
    s = _norm(v).replace("\u0307", "")
    for a, b in (("ı", "i"), ("ğ", "g"), ("ş", "s"), ("ç", "c"), ("ö", "o"), ("ü", "u")):
        s = s.replace(a, b)
    return s


def _locations_from_static() -> dict[str, set[str]]:
    """search/data/tr_il_ilce.json: {"Çanakkale": ["Ayvacık", ...], ...}
    Galeri verisinde hiç ilan olmayan il/ilçeler de seçilebilsin diye."""
    try:
        with open(_TR_LOCATIONS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {str(city): {str(d) for d in districts} for city, districts in data.items()}


def load_locations(force: bool = False) -> list[dict]:
    """[{"city": "İstanbul", "districts": ["Ataşehir", ...]}, ...]

    Galeri DB'si ana kaynak, `search_listing` adresleri üstüne ekleniyor.
    Sonuç 6 saat cache'lenir — iki kaynak da gün içinde değişmiyor.
    """
    if not force:
        cached = cache.get(_LOCATIONS_CACHE_KEY)
        if cached is not None:
            return cached

    # Sabit 81 il / tüm ilçeler temel kaynak; veri kaynakları üstüne eklenir.
    # Yazım farklarını (İstanbul/Istanbul, EZİNE/Ezine) tek kayıtta topla:
    # ilk görülen yazım (sabit liste) kazanır.
    merged: dict[str, set[str]] = {}
    city_names: dict[str, str] = {}
    district_names: dict[tuple[str, str], str] = {}
    for source in (_locations_from_static(), _locations_from_galeri(), _locations_from_listings()):
        for city, districts in source.items():
            ckey = _loc_key(city)
            if not ckey:
                continue
            name = city_names.setdefault(ckey, city)
            bucket = merged.setdefault(name, set())
            for district in districts:
                dkey = (ckey, _loc_key(district))
                if dkey[1] and dkey not in district_names:
                    district_names[dkey] = district
                    bucket.add(district)

    result = [
        {"city": city, "districts": sorted(merged[city], key=_tr_key)}
        for city in sorted(merged, key=_tr_key)
    ]
    cache.set(_LOCATIONS_CACHE_KEY, result, _LOCATIONS_TTL)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 2) Araç varsayılanları (vites vb.)
# ═══════════════════════════════════════════════════════════════════════════

def vehicle_defaults(*, brand: str, series: str, engine: str = "",
                     package: str | None = None, **_ignored) -> dict:
    """Seçilen araç için `search_listing`'de en sık görülen vitesi döndürür.
    Kullanıcı istediği zaman üzerine yazabilir — bu sadece ön doldurma."""
    from ..models import Listing

    gear_default = ""
    try:
        qs = Listing.objects.exclude(gear="")
        if brand:
            qs = qs.filter(brand__iexact=brand)
        if series:
            qs = qs.filter(Q(model__icontains=series) | Q(title__icontains=series))
        if engine:
            narrowed = qs.filter(title__icontains=engine)
            if narrowed.exists():
                qs = narrowed
        counts: dict[str, int] = {}
        for gear in qs.values_list("gear", flat=True)[:4000]:
            gear = str(gear or "").strip()
            if gear:
                counts[gear] = counts.get(gear, 0) + 1
        if counts:
            gear_default = max(counts, key=counts.get)
    except Exception:
        gear_default = ""

    return {"gear_default": gear_default}


# ═══════════════════════════════════════════════════════════════════════════
# 3) Analiz
# ═══════════════════════════════════════════════════════════════════════════

_ANNUAL_KM = 15_000          # değer kaybı projeksiyonunda yıllık km varsayımı
_TREND_DAYS = 90             # fiyat trendi penceresi
_YEAR_TOLERANCE = 1          # emsal ilan seçiminde ±yıl


def _galeri_groups(brand: str, series: str, year: int) -> list[dict]:
    """galeri_summary.json'dan (marka, seri, yıl±tolerans) eşleşen özet
    gruplar. Eskiden burada SQLite'a 4 ayrı sorgu atılırdı; artık RAM'deki
    JSON'dan sözlük okuma."""
    return galeri_summary.groups_for(brand, series, year, _YEAR_TOLERANCE)


def _week_start_date(week_label: str) -> str:
    """"2026-W25" -> o haftanın Pazartesi günü (ISO 8601)."""
    try:
        year_s, week_s = week_label.split("-W")
        return date.fromisocalendar(int(year_s), int(week_s), 1).isoformat()
    except (ValueError, AttributeError, TypeError):
        return week_label


def _price_trend(groups: list[dict]) -> list[dict]:
    """Haftalık ortalama ilan fiyatı (±yıl toleransındaki gruplar birleştirilerek).
    Frontend `snapshot_date` / `avg_price` / `sample_count` bekliyor; hafta
    başlangıcı (Pazartesi) `snapshot_date` olarak veriliyor. Son ~13 hafta
    (eski `_TREND_DAYS`li pencereye yakın) gösterilir."""
    weekly: dict[str, list[float]] = {}
    for g in groups:
        for point in g.get("price_trend") or []:
            week = point.get("week")
            count = int(point.get("count") or 0)
            avg = point.get("avg_price")
            if not week or not count or avg is None:
                continue
            total, n = weekly.get(week, (0.0, 0))
            weekly[week] = (total + avg * count, n + count)
    return [
        {
            "snapshot_date": _week_start_date(week),
            "avg_price": round(total / n),
            "sample_count": n,
        }
        for week, (total, n) in sorted(weekly.items())[-13:]
    ]


def _regional_signal(groups: list[dict], city: str, district: str) -> dict:
    """Seçilen ilin ortalaması ülke ortalamasının neresinde?

    city boş bırakılabilir (B2C'de opsiyonel) — o durumda label "Bölge
    seçilmedi" döner. Not: galeri özet verisi il bazında tutuluyor (ilçe
    kırılımı yok); `district` geriye dönük uyumluluk için parametrede kalıyor.
    """
    if not city:
        return {
            "city": "", "district": "",
            "label": "Bölge belirtilmedi",
            "confidence_pct": 0, "delta_pct": None,
        }

    city_key = _norm(city)
    local_total = local_count = 0.0
    national_total = national_count = 0.0
    for g in groups:
        for c_name, c_info in (g.get("cities") or {}).items():
            cnt = int(c_info.get("count") or 0)
            avg = c_info.get("avg_price")
            if not cnt or avg is None:
                continue
            national_total += avg * cnt
            national_count += cnt
            if _norm(c_name) == city_key:
                local_total += avg * cnt
                local_count += cnt

    if local_count < 5 or not national_count:
        return {
            "city": city, "district": district,
            "label": "Bu bölge için yeterli ilan verisi yok",
            "confidence_pct": 0, "delta_pct": None,
        }

    local_avg = local_total / local_count
    national_avg = national_total / national_count
    delta_pct = (local_avg - national_avg) / national_avg * 100 if national_avg else 0

    if delta_pct >= 4:
        label = f"{city} ülke ortalamasının %{abs(delta_pct):.1f} üzerinde — burada satmak avantajlı"
    elif delta_pct <= -4:
        label = f"{city} ülke ortalamasının %{abs(delta_pct):.1f} altında — burada almak avantajlı"
    else:
        label = f"{city} fiyatları ülke ortalamasıyla uyumlu"

    return {
        "city": city,
        "district": district,
        "label": label,
        "confidence_pct": int(min(90, 40 + local_count)),
        "delta_pct": round(delta_pct, 1),
    }


def _color_adjustment(groups: list[dict], color: str | None) -> dict | None:
    """Renk, aynı modelin ortalamasına göre ne kadar prim/iskonto getiriyor?
    Örneklem küçükse None döner (frontend `?.` ile güvenli okuyor).

    galeri_summary.json her grubun kendi renk faktörünü o grubun medyan
    fiyatına göre tutuyor; burada grup medyanları taban alınarak (marka,
    seri, yıl±tolerans) genelinde ağırlıklı ortalanıyor."""
    if not color:
        return None
    color_key = _norm(color)
    color_price_total = color_count = 0.0
    base_price_total = base_count = 0.0
    for g in groups:
        median = g.get("median_price")
        sample_count = g.get("sample_count") or 0
        if median is None or not sample_count:
            continue
        base_price_total += median * sample_count
        base_count += sample_count
        for c_name, c_info in (g.get("colors") or {}).items():
            if _norm(c_name) != color_key:
                continue
            cnt = int(c_info.get("sample_count") or 0)
            factor_pct = c_info.get("factor_pct")
            if not cnt or factor_pct is None:
                continue
            color_price_total += median * (1 + factor_pct / 100) * cnt
            color_count += cnt

    if color_count < 8 or base_count < 20:
        return None
    base = base_price_total / base_count
    if not base:
        return None
    color_avg = color_price_total / color_count
    factor_pct = (color_avg - base) / base * 100
    return {
        "color": color,
        "factor_pct": round(factor_pct, 1),
        "sample_count": int(color_count),
    }


def _listing_matches(brand: str, series: str, year: int) -> int:
    from ..models import Listing
    try:
        return (
            Listing.objects.filter(brand__iexact=brand)
            .filter(Q(model__icontains=series) | Q(title__icontains=series))
            .filter(year__gte=year - _YEAR_TOLERANCE, year__lte=year + _YEAR_TOLERANCE)
            .count()
        )
    except Exception:
        return 0


# ── Paket bilinmediğinde tahmin ─────────────────────────────────────────────
#
# central_price_estimator paket referansına dayanıyor: paket verilmezse
# "Paket referansı bulunamadı." döner ve TÜM analiz belirsize düşer. B2C'de
# paket opsiyonel olduğu için (son kullanıcı çoğu zaman paketini bilmez)
# burada seriye/motora ait BÜTÜN paketler için tahmin çalıştırılıp medyan
# alınıyor. Aralık, paketler arası gerçek yayılımı gösterir -- yani "hangi
# paket olduğu bilinmiyor" belirsizliği fiyat aralığına dürüstçe yansır.

def _engine_packages(category: str, brand: str, series: str, engine: str) -> list[str]:
    from .arabam_vehicles_service import load_arabam_vehicles
    try:
        catalog = load_arabam_vehicles()
    except Exception:
        return []
    for entry in catalog:
        if entry.get("category") != category or _norm(entry.get("name")) != _norm(brand):
            continue
        for series_entry in entry.get("series") or []:
            if _norm(series_entry.get("name")) != _norm(series):
                continue
            for engine_entry in series_entry.get("engines") or []:
                if _norm(engine_entry.get("name")) != _norm(engine):
                    variants = engine_entry.get("variants") or []
                    if variants:
                        continue
                    continue
                names = [v.get("name") for v in (engine_entry.get("variants") or [])]
                if not names:
                    names = [v.get("name") for v in (series_entry.get("variants") or [])]
                return [n for n in names if n]
    return []


def _estimate_vehicle(*, category: str, brand: str, series: str, engine: str,
                      package: str | None, year: int, km: float, damage: list,
                      agir_hasar: bool, gear: str | None, **extra) -> dict:
    """estimate_price sarmalayıcısı + paket bilinmiyorsa medyan geri düşüşü."""
    from .price_estimator import estimate as estimate_price

    def _run(pkg, **more):
        return estimate_price(
            category=category, brand=brand, series=series, engine=engine,
            package=pkg, year=year, km=km, damage=damage,
            agir_hasar=agir_hasar, gear=gear, **extra, **more,
        )

    result = _run(package)
    if result.get("found"):
        return result

    # Seçilen paketin kendi referansı yoksa ya da çok az ilana dayanıyorsa
    # (bkz. MIN_PAKET_SAMPLES) analiz eskiden komple boş dönüyordu. Artık
    # aynı motorun DİĞER paketlerinden medyan alınıyor -- paket seçilmemiş
    # gibi. Paket bilgisi kaybolduğu için güven düşürülür ve kullanıcıya
    # hangi paketlerin kullanıldığı söylenir.
    candidates = _engine_packages(category, brand, series, engine)
    priced: list[tuple[str, dict]] = []
    for name in candidates[:20]:                # aşırı uzun serilerde sınır
        if package and _norm(name) == _norm(package):
            continue
        try:
            candidate = _run(name)
        except Exception:
            continue
        if candidate.get("found") and candidate.get("tahmini_fiyat"):
            priced.append((name, candidate))

    if not priced:
        # Son çare: tek-iki ilana dayanan zayıf referans. Hiç tahmin
        # vermemektense, "çok belirsiz" etiketiyle vermek daha yararlı.
        thin = _run(package, min_samples=1)
        if thin.get("found") and thin.get("tahmini_fiyat"):
            value = int(thin["tahmini_fiyat"])
            thin.update({
                "estimated_low": int(round(value * 0.72 / 1000) * 1000),
                "estimated_high": int(round(value * 1.28 / 1000) * 1000),
                "confidence_pct": 20,
                "fallback_reason": (
                    "Bu paket için referans veri çok sınırlı; tahmin çok belirsiz, "
                    "geniş bir aralık olarak okuyun."
                ),
            })
            return thin
        return result

    values = sorted(c["tahmini_fiyat"] for _, c in priced)
    middle = len(values) // 2
    median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) // 2

    merged = dict(priced[len(priced) // 2][1])
    # Aralık, paketler arası yayılım ile motorun kendi ±%18 bandının
    # BİRLEŞİMİ. Sadece yayılımı almak, paketler birbirine yakın olduğunda
    # "paketi bilmiyoruz" durumunu bilinen pakete göre DAHA DAR gösterirdi --
    # daha az bilgi asla daha dar aralık üretmemeli.
    band = 0.18
    low = min(int(min(values)), int(median * (1 - band)))
    high = max(int(max(values)), int(median * (1 + band)))
    merged.update({
        "found": True,
        "tahmini_fiyat": int(median),
        "estimated_low": int(round(low / 1000) * 1000),
        "estimated_high": int(round(high / 1000) * 1000),
        # Paket bilinmiyor -> güven düşük. Tek paket eşleştiğinde bile 45'i
        # geçmiyor, çünkü hangi paket olduğu hâlâ doğrulanmış değil.
        "confidence_pct": int(min(45, 25 + 4 * len(priced))),
        "fallback_reason": (
            f"Paket seçilmediği için {len(priced)} paketin tahmini hesaplanıp medyanı "
            "alındı. Paketi seçerseniz tahmin belirgin şekilde daralır."
            if not package else
            f"“{package}” paketi için yeterli referans ilan yok; aynı motorun "
            f"{len(priced)} paketinin ({', '.join(n for n, _ in priced)}) medyanı kullanıldı."
        ),
        "package_fallback": {"count": len(priced), "packages": [n for n, _ in priced]},
    })
    return merged

def _decision(price: int | None, estimate_value: int | None) -> dict:
    """İlan fiyatının tahmine göre sapmasından tek bir karar üretir.

    Eşikler sabit ve açıkça yazılı (LLM yorumu yok) — aynı girdi her zaman
    aynı kararı verir.
    """
    if not price or not estimate_value:
        return {
            "label": "Belirsiz",
            "title": "Yeterli referans veri yok",
            "score": 0.0,
            "deviation_pct": 0.0,
        }
    deviation = (price - estimate_value) / estimate_value * 100

    if deviation <= -12:
        label, title = "Fırsat", "Piyasanın belirgin altında — fırsat"
    elif deviation <= -4:
        label, title = "Uygun", "Piyasanın hafif altında — uygun fiyat"
    elif deviation < 6:
        label, title = "Piyasa", "Piyasa değerine yakın"
    elif deviation < 15:
        label, title = "Pahalı", "Piyasanın üzerinde — pazarlık şart"
    else:
        label, title = "Çok pahalı", "Piyasanın belirgin üzerinde — uzak durun"

    # ÖLÇEK: 0-10. Arayüz (decision-card > score-ring) puanı sabit "/10"
    # ile basıyor -- 100'lük ölçek gönderilirse "65/10" gibi görünür.
    # -25% sapma 10 puan, +25% sapma 0 puan, piyasa fiyatı 5 puan.
    score = round(max(0.0, min(10.0, 5 - deviation / 5)), 1)
    return {
        "label": label,
        "title": title,
        "score": score,
        "deviation_pct": round(deviation, 1),
    }


def _negotiation(price: int | None, estimate: dict) -> dict:
    value = estimate.get("tahmini_fiyat")
    low = estimate.get("estimated_low")
    if not price or not value or not low:
        return {
            "available": False,
            "reason": "Bu araç için yeterli referans veri bulunamadığından pazarlık planı çıkarılamadı.",
            "note": "", "target_price": None, "opening_offer": None,
            "ceiling_price": None, "potential_saving": None,
        }
    if price < value:
        target = int(round(price * 0.95 / 1000) * 1000)
        opening = int(round(price * 0.92 / 1000) * 1000)
        return {
            "available": True,
            "reason": "",
            "note": (
                "İlan fiyatı tahmini piyasa değerinin altında olduğu için pazarlık "
                "planı ilan fiyatı üzerinden kuruldu: hedef fiyat ilan fiyatının %5 "
                "altına, açılış teklifi %8 altına konumlandırıldı. İlan fiyatı tavan kabul edildi."
            ),
            "target_price": target,
            "opening_offer": opening,
            "ceiling_price": price,
            "potential_saving": max(0, price - target),
        }

    target = int(round(min(price, value * 0.96) / 1000) * 1000)
    opening = int(round(max(low * 0.97, target * 0.94) / 1000) * 1000)
    ceiling = int(round(min(price, value * 1.02) / 1000) * 1000)
    return {
        "available": True,
        "reason": "",
        "note": (
            "Açılış teklifi tahmini aralığın alt sınırına, hedef fiyat tahmini "
            "piyasa değerinin %4 altına konumlandırıldı. Tavan fiyatın üzerine "
            "çıkmak bu araçta piyasa priminde alım demek."
        ),
        "target_price": target,
        "opening_offer": opening,
        "ceiling_price": ceiling,
        "potential_saving": max(0, price - target),
    }


def _depreciation(*, category: str, brand: str, series: str, engine: str,
                  package: str | None, year: int, km: float, damage: list,
                  agir_hasar: bool, gear: str | None,
                  current_value: int | None) -> dict:
    """1 ve 3 yıl sonraki tahmini değer.

    Ayrı bir "değer kaybı modeli" uydurmak yerine AYNI tahmin motoru
    yeniden çağrılıyor: bugün X model yılı / Y km olan araç, n yıl sonra
    (X-n) model yılı / (Y + n*15.000) km'lik bir araca denk gelir.
    """
    if not current_value:
        return {
            "available": False,
            "reason": "Güncel değer hesaplanamadığı için projeksiyon yapılamadı.",
            "note": "", "current_value": None,
            "one_year_value": None, "one_year_loss": None,
            "three_year_value": None, "three_year_loss": None,
        }

    def value_after(years: int) -> int | None:
        try:
            res = _estimate_vehicle(
                category=category, brand=brand, series=series, engine=engine,
                package=package, year=year - years, km=km + years * _ANNUAL_KM,
                damage=damage, agir_hasar=agir_hasar, gear=gear,
            )
            return res.get("tahmini_fiyat")
        except Exception:
            return None

    one = value_after(1)
    three = value_after(3)
    if not one or not three:
        return {
            "available": False,
            "reason": "Daha eski model yılları için referans paket verisi bulunamadı.",
            "note": "", "current_value": current_value,
            "one_year_value": None, "one_year_loss": None,
            "three_year_value": None, "three_year_loss": None,
        }

    return {
        "available": True,
        "reason": "",
        # NOT: sayıyı ayrı formatla -- f-string'in tamamına .replace(",", ".")
        # uygulamak cümledeki normal virgülleri de noktaya çevirirdi.
        "note": (
            f"Yılda {_ANNUAL_KM:,}".replace(",", ".")
            + " km kullanım varsayımıyla, aynı tahmin motorunun bir ve üç yaş "
              "büyük emsallere verdiği değerler."
        ),
        "current_value": current_value,
        "one_year_value": one,
        "one_year_loss": max(0, current_value - one),
        "three_year_value": three,
        "three_year_loss": max(0, current_value - three),
    }


def _listing_quality(*, km: float, year: int, damage: list, agir_hasar: bool,
                     color: str | None, gear: str | None,
                     city: str, deviation_pct: float,
                     description: dict | None = None) -> dict:
    """İlanın veri riski. Objektif, sabit eşikli kurallar — puan bunlardan
    düşülerek hesaplanıyor, yorum katılmıyor.

    `deductions`: her uyarının 100 üzerinden kaç puan götürdüğü. `warnings`
    ile birebir aynı sırada ve aynı metinlerle döner; arayüz uyarıları
    ağırlığa göre sıralayabilsin diye eklendi.
    """
    warnings: list[str] = []
    deductions: list[dict] = []
    score = 100
    age = max(datetime.now().year - int(year), 0)

    def penalize(text: str, points: int) -> None:
        nonlocal score
        warnings.append(text)
        deductions.append({"label": text, "points": points})
        score -= points

    if agir_hasar:
        penalize("Ağır hasar kaydı var — ekspertiz ve tramer sorgusu şart.", 35)
    changed = [d for d in damage if "değiş" in _norm(d.get("durum"))]
    painted = [d for d in damage if "boya" in _norm(d.get("durum"))]
    if len(changed) >= 3:
        penalize(f"{len(changed)} parça değişmiş — yapısal onarım ihtimali yüksek.", 25)
    elif changed:
        penalize(f"{len(changed)} parça değişmiş.", 10)
    if len(painted) >= 5:
        penalize(f"{len(painted)} parça boyalı — geniş çaplı boya işlemi.", 15)

    if age and km / age > 35_000:
        penalize(f"Yıllık ortalama {round(km / age):,} km — yoğun kullanım.".replace(",", "."), 10)
    if km >= 300_000:
        penalize("300.000 km üzeri — büyük bakım kalemleri gündeme gelmiş olabilir.", 10)

    if deviation_pct <= -20:
        penalize("Fiyat piyasanın çok altında — ilanda belirtilmeyen bir kusur olabilir.", 15)

    if not color:
        penalize("Renk belirtilmedi — değerlemede renk primi hesaplanamadı.", 3)
    if not gear:
        penalize("Vites tipi belirtilmedi — tahmin doğruluğu düşer.", 3)
    if not city:
        penalize("İl seçilmedi — bölgesel fiyat farkı analize katılamadı.", 3)

    # ── Açıklama metninden gelen sinyaller ───────────────────────────────
    if description and description.get("available"):
        for contradiction in description.get("contradictions") or []:
            penalize(
                f"Çelişki: \u201c{contradiction['claim']}\u201d — {contradiction['conflict']}",
                12,
            )
        for flag in description.get("red_flags") or []:
            if flag not in warnings:
                penalize(flag, 0)
        if (description.get("score") or 0) <= 3:
            penalize("İlan açıklaması çok zayıf — satıcı bilgi paylaşmaktan kaçınıyor olabilir.", 8)
        if description.get("missing"):
            penalize(
                "Açıklamada hiç değinilmemiş: " + ", ".join(description["missing"]).lower() + ".",
                3 * len(description["missing"]),
            )
    else:
        penalize("İlan açıklaması girilmedi — metin analizi yapılamadı.", 5)

    score = int(max(0, min(100, score)))
    if score >= 80:
        label = "Düşük risk"
    elif score >= 55:
        label = "Orta risk"
    else:
        label = "Yüksek risk"
    return {"label": label, "score": score, "warnings": warnings,
            "deductions": [d for d in deductions if d["points"] > 0]}


def _questions(*, damage: list, agir_hasar: bool, km: float, year: int,
               package: str | None, color: str | None,
               description: dict | None = None) -> list[dict]:
    """Satıcıya sorulacaklar — verilmeyen/riskli alanlardan türetilir."""
    out: list[dict] = []
    age = max(datetime.now().year - int(year), 0)

    if agir_hasar:
        out.append({
            "question": "Ağır hasar kaydı hangi olaydan kaynaklanıyor?",
            "reason": " Onarım faturaları ve ekspertiz raporu talep edin; şasi/airbag kaydı varsa değer ciddi düşer.",
        })
    changed = [d.get("parca") for d in damage if "değiş" in _norm(d.get("durum"))]
    if changed:
        out.append({
            "question": f"Değişen parçalar ({', '.join(str(c) for c in changed[:4])}) neden değişti?",
            "reason": " Orijinal parça mı takıldı, işlem yetkili serviste mi yapıldı öğrenin.",
        })
    if not damage:
        out.append({
            "question": "Aracın tramer kaydı ve boya-değişen durumu nedir?",
            "reason": " Hasar bilgisi girilmedi; tramer sorgusu olmadan tahmin hasarsız kabul edilerek yapıldı.",
        })
    if age >= 5 or km >= 150_000:
        out.append({
            "question": "Triger seti / kayışı ve debriyaj en son ne zaman değişti?",
            "reason": " Bu yaş ve kilometrede yaklaşan büyük bakım kalemleri pazarlık kozudur.",
        })
    out.append({
        "question": "Araç kaç kişinin üzerine kayıtlıydı ve ruhsatta hasar/rehin şerhi var mı?",
        "reason": " Sık el değiştiren araçlar ile rehinli araçlar satışta değer kaybeder.",
    })
    if not package:
        out.append({
            "question": "Aracın tam donanım paketi nedir?",
            "reason": " Paket seçilmediği için tahmin seri ortalaması üzerinden yapıldı.",
        })
    if not color:
        out.append({
            "question": "Aracın rengi nedir, boyasız mı?",
            "reason": " Renk ikinci elde %5'e varan fark yaratabiliyor.",
        })

    # Açıklamadaki çelişkiler en öncelikli sorular -- başa alınır.
    if description and description.get("available"):
        priority: list[dict] = []
        for contradiction in description.get("contradictions") or []:
            priority.append({
                "question": f"İlanda \u201c{contradiction['claim']}\u201d yazıyor — bunu teyit eder misiniz?",
                "reason": f" {contradiction['conflict']} Bu çelişki netleşmeden fiyat konuşmayın.",
            })
        for topic in description.get("missing") or []:
            priority.append({
                "question": f"{topic} hakkında bilgi verir misiniz?",
                "reason": " İlan açıklamasında bu konuya hiç değinilmemiş.",
            })
        out = priority + out

    # Aynı soru iki kaynaktan gelebiliyor -- sırayı bozmadan tekille.
    seen: set[str] = set()
    unique: list[dict] = []
    for item in out:
        if item["question"] not in seen:
            seen.add(item["question"])
            unique.append(item)
    return unique


def _price_factors(estimate: dict, color_adjustment: dict | None,
                   regional: dict) -> list[dict]:
    """Tahmine uygulanan çarpanları yüzde etkisine çevirir. Motorun kendi
    döndürdüğü katsayılar kullanılır — burada yeniden hesaplanmaz."""
    factors: list[dict] = []

    def add(label: str, factor: Any, note: str) -> None:
        try:
            pct = (float(factor) - 1) * 100
        except (TypeError, ValueError):
            return
        if abs(pct) < 0.05:
            return
        factors.append({"label": label, "note": note, "effect_pct": round(pct, 1)})

    add("Kilometre", estimate.get("km_factor"), "Aracın kilometresinin fiyata etkisi")
    add("Hasar durumu", estimate.get("damage_factor"),
        "Boyalı/değişen parçaların toplam etkisi")
    add("Vites", estimate.get("gear_factor"),
        "Manuel araçlar ikinci elde daha yavaş satılıyor")

    if color_adjustment:
        factors.append({
            "label": f"Renk: {color_adjustment['color']}",
            "note": f"{color_adjustment['sample_count']} emsal galeri ilanına göre",
            "effect_pct": color_adjustment["factor_pct"],
        })
    # Bölge etkisi ayrı "Bölge analizi" bölümünde gösteriliyor; burada
    # %0 etkili tekrar satır çıkarmıyoruz.
    return factors


@lru_cache(maxsize=512)
def _evidence_counts(brand: str, series: str, year: int, year_lo: int, year_hi: int,
                     _version: str) -> tuple:
    """Kanıt sayaçları (benzersiz araç/galeri, yayındakiler) — galeri_summary.json
    ve galeri_latest_snapshot.json'dan. Girdileri aynı olan analizler için tekrar
    hesaplanmaz; veri dosyaları değişince _version anahtarı yeniler.

    Not: `unique_vehicles` gruplar arası toplanır (her yıl grubu farklı araçlar
    içerir); `unique_sellers` gruplar arası MAX alınır (aynı galeri birden çok
    yılda satış yapabilir, toplarsak abartılı sayar) — ikisi de eski tekil
    SQL sorgusunun birebir aynısı değil, yakın bir üst sınırdır."""
    groups = galeri_summary.groups_for(brand, series, year, _YEAR_TOLERANCE)
    unique_vehicles = sum(int(g.get("unique_vehicles") or 0) for g in groups)
    unique_sellers = max((int(g.get("unique_sellers") or 0) for g in groups), default=0)
    same_year = next(
        (int(g.get("unique_vehicles") or 0) for g in groups if g.get("year") == year), 0
    )
    latest = max(
        (g.get("latest_date") for g in groups if g.get("latest_date")), default=None
    )

    brand_key, series_key = _norm(brand), _norm(series)
    live_now = sum(
        1 for row in galeri_summary.latest_snapshot().get("listings", [])
        if _norm(row.get("brand")) == brand_key and _norm(row.get("series")) == series_key
        and row.get("year") is not None and year_lo <= row["year"] <= year_hi
        and row.get("price") is not None and _MIN_REAL_PRICE <= row["price"] <= _MAX_REAL_PRICE
    )
    return unique_vehicles, unique_sellers, same_year, latest, live_now


def _evidence(estimate: dict, *, brand: str, series: str, year: int, package: str | None) -> dict:
    """Tahminin arkasındaki kanıt: kaç referans ilan, paket birebir mi, kaç
    benzersiz emsal araç / galeri, veri ne kadar taze. Snapshot satır sayısı değil,
    benzersiz ilan (listing_key) sayılır -- aynı araç her gün tekrar sayılmasın."""
    found = bool(estimate.get("found"))
    fallback = estimate.get("package_fallback")
    if not found:
        trim_match = "none"
    elif fallback:
        trim_match = "engine_median"
    elif package:
        trim_match = "exact"
    else:
        trim_match = "engine"
    reference_count = int(estimate.get("base_count") or 0) if found else 0

    unique_vehicles = unique_sellers = same_year = live_now = 0
    latest = None
    try:
        unique_vehicles, unique_sellers, same_year, latest, live_now = _evidence_counts(
            brand, series, year, year - _YEAR_TOLERANCE, year + _YEAR_TOLERANCE, _data_version())
    except Exception:
        pass

    days_old = None
    if latest:
        try:
            days_old = max(0, (datetime.now().date() - datetime.strptime(str(latest)[:10], "%Y-%m-%d").date()).days)
        except ValueError:
            days_old = None

    points = 0
    points += 2 if trim_match == "exact" else (1 if trim_match == "engine" else 0)
    points += 1 if reference_count >= 5 else 0
    points += 1 if (unique_vehicles or 0) >= 20 else 0
    points += 1 if days_old is not None and days_old <= 14 else 0
    strength = "strong" if points >= 4 else ("medium" if points >= 2 else "weak")

    notes = []
    if trim_match == "exact":
        notes.append("Tahmin, seçtiğiniz paketin kendi referans ilanlarından hesaplandı.")
    elif trim_match == "engine_median" and package:
        notes.append(f"“{package}” paketi için yeterli referans ilan yok; aynı motorun {fallback['count']} paketinin ortalaması kullanıldı.")
    elif trim_match == "engine_median":
        notes.append(f"Paket seçilmediği için {fallback['count']} paketin ortalaması kullanıldı; paketi seçmek tahmini netleştirir.")
    elif trim_match == "engine":
        notes.append("Paket belirtilmedi; motor seviyesinde eşleşme kullanıldı.")
    else:
        notes.append("Bu araç için referans fiyat bulunamadı.")
    if found and reference_count < 5:
        notes.append("Bu araç için referans veri sınırlı; tahmin daha belirsiz.")
    if (unique_vehicles or 0) < 10:
        notes.append("Son 90 günde az sayıda benzer araç bulundu.")
    if days_old is not None and days_old > 14:
        notes.append(f"Piyasa verisi {days_old} gün önce güncellendi.")

    return {
        "strength": strength,
        "trim_match": trim_match,
        "reference_listings": reference_count,
        "gear_specific": bool(estimate.get("used_real_gear_data")),
        "unique_comparables": int(unique_vehicles or 0),
        "unique_sellers": int(unique_sellers or 0),
        "same_year_comparables": int(same_year or 0),
        "live_comparables": int(live_now or 0),
        "window_days": _TREND_DAYS,
        "data_date": str(latest)[:10] if latest else None,
        "data_age_days": days_old,
        "notes": notes,
    }


def scenario(payload: dict) -> dict:
    """"Ne olurdu?" senaryosu: sadece tahmin, karar ve pazarlık."""
    category = str(payload.get("category") or "otomobil").strip() or "otomobil"
    brand = str(payload.get("brand") or "").strip()
    series = str(payload.get("series") or "").strip()
    engine = str(payload.get("engine") or "").strip()
    package = (str(payload.get("package")).strip() or None) if payload.get("package") else None
    city = str(payload.get("city") or "").strip()
    fuel = str(payload.get("fuel") or "").strip() or None
    gear = str(payload.get("gear") or "").strip() or None
    agir_hasar = str(payload.get("agir_hasar", False)).strip().lower() in {"1", "true", "evet", "yes"}
    damage = payload.get("damage") or []
    if not isinstance(damage, list):
        raise ValueError("damage bir liste olmalıdır.")
    year = int(payload["year"])
    km = float(payload["km"])
    price = int(float(payload["price"]))
    estimate = _estimate_vehicle(
        category=category, brand=brand, series=series, engine=engine,
        package=package, year=year, km=km, damage=damage,
        agir_hasar=agir_hasar, gear=gear, fuel=fuel, city=city or None,
    )
    value = estimate.get("tahmini_fiyat")
    return {
        "estimate": {
            "tahmini_fiyat": value,
            "estimated_low": estimate.get("estimated_low"),
            "estimated_high": estimate.get("estimated_high"),
            "confidence_pct": estimate.get("confidence_pct") or 0,
            "fallback_reason": estimate.get("fallback_reason"),
        },
        "decision": _decision(price, value),
        "negotiation": _negotiation(price, estimate),
    }


def _data_version() -> str:
    """Referans dosyaları değişince (yeni snapshot) analiz cache'i kendiliğinden geçersiz olur."""
    parts = []
    for path in (settings.B2C_GALERI_SUMMARY, settings.B2C_GALERI_LATEST_SNAPSHOT, settings.B2C_BASELINE_DB):
        try:
            parts.append(str(os.stat(path).st_mtime_ns))
        except OSError:
            parts.append("0")
    return "-".join(parts)


def analyze_cached(payload: dict) -> dict:
    """`analyze` + Redis cache. Aynı girdi, aynı veri sürümü => aynı sonuç (motor deterministik)."""
    ttl = int(getattr(settings, "B2C_ANALYSIS_CACHE_TTL", 0) or 0)
    if ttl <= 0:
        return analyze(payload)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
    key = f"b2c:analyze:v1:{_data_version()}:{digest}"
    try:
        hit = cache.get(key)
    except Exception:
        hit = None
    if hit is not None:
        hit = copy.deepcopy(hit)
        hit["generated_at"] = datetime.now().isoformat(timespec="seconds")
        return hit
    result = analyze(payload)
    try:
        cache.set(key, result, ttl)
    except Exception:
        pass
    return copy.deepcopy(result)


def analyze(payload: dict) -> dict:
    """B2C tam analiz. `city` / `district` OPSİYONELDİR — verilmezse bölgesel
    sinyal ve renk primi dışındaki her şey aynen hesaplanır."""
    from .tco import compute_tco
    from .vehicle_traits import analiz_icin as _arac_ozellikleri

    category = str(payload.get("category") or "otomobil").strip() or "otomobil"
    brand = str(payload.get("brand") or "").strip()
    series = str(payload.get("series") or "").strip()
    engine = str(payload.get("engine") or "").strip()
    package = (str(payload.get("package")).strip() or None) if payload.get("package") else None
    city = str(payload.get("city") or "").strip()
    district = str(payload.get("district") or "").strip()
    color = (str(payload.get("color")).strip() or None) if payload.get("color") else None
    fuel = str(payload.get("fuel") or "").strip() or None
    gear = str(payload.get("gear") or "").strip() or None
    agir_hasar = str(payload.get("agir_hasar", False)).strip().lower() in {"1", "true", "evet", "yes"}
    damage = payload.get("damage") or []
    if not isinstance(damage, list):
        raise ValueError("damage bir liste olmalıdır.")

    year = int(payload["year"])
    km = float(payload["km"])
    price = int(float(payload["price"]))
    description_text = str(payload.get("description") or "").strip()

    estimate = _estimate_vehicle(
        category=category, brand=brand, series=series, engine=engine,
        package=package, year=year, km=km, damage=damage,
        agir_hasar=agir_hasar, gear=gear, fuel=fuel, city=city or None,
    )
    value = estimate.get("tahmini_fiyat")

    galeri_groups = _galeri_groups(brand, series, year)
    trend = _price_trend(galeri_groups)
    regional = _regional_signal(galeri_groups, city, district)
    color_adjustment = _color_adjustment(galeri_groups, color)
    decision = _decision(price, value)
    description_analysis = description_insights(
        description_text, damage=damage, agir_hasar=agir_hasar, km=km, year=year,
        price=price,
    )
    similar = similar_listings(brand, series, year, price)

    estimate_out = {
        "tahmini_fiyat": value,
        "estimated_low": estimate.get("estimated_low"),
        "estimated_high": estimate.get("estimated_high"),
        "confidence_pct": estimate.get("confidence_pct") or 0,
        "color_adjustment": color_adjustment,
        "fallback_reason": estimate.get("fallback_reason"),
        "package_fallback": estimate.get("package_fallback"),
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "vehicle": {
            "brand": brand, "series": series, "engine": engine,
            "package": package, "year": year, "km": km,
            "color": color, "city": city, "district": district,
            "price": price,
        },
        "estimate": estimate_out,
        "decision": decision,
        "negotiation": _negotiation(price, estimate),
        "depreciation": _depreciation(
            category=category, brand=brand, series=series, engine=engine,
            package=package, year=year, km=km, damage=damage,
            agir_hasar=agir_hasar, gear=gear, current_value=value,
        ),
        "listing_quality": _listing_quality(
            km=km, year=year, damage=damage, agir_hasar=agir_hasar,
            color=color, gear=gear, city=city,
            deviation_pct=decision["deviation_pct"],
            description=description_analysis,
        ),
        "description_analysis": description_analysis,
        "similar_listings": similar,
        "questions": _questions(
            damage=damage, agir_hasar=agir_hasar, km=km, year=year,
            package=package, color=color, description=description_analysis,
        ),
        "price_factors": _price_factors(estimate, color_adjustment, regional),
        "price_trend": trend,
        "regional_signal": regional,
        "tco": compute_tco(engine=engine, year=year, estimated_value=value,
                           annual_km=_ANNUAL_KM),
        # Kronik / iyi / kötü özellikler: hazır veritabanından salt okuma.
        # Veri yoksa available=False döner, kart boş durumunu gösterir.
        "vehicle_traits": _arac_ozellikleri(brand, series, engine),
        "evidence": _evidence(estimate, brand=brand, series=series, year=year, package=package),
        "data_sources": {
            "gallery_matches": sum(int(g.get("sample_count") or 0) for g in galeri_groups),
            "listing_matches": _listing_matches(brand, series, year),
            "trend_points": len(trend),
            "similar_listings": len(similar),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4) İlan açıklaması — anlam çıkarımı
# ═══════════════════════════════════════════════════════════════════════════
#
# LLM KULLANILMIYOR. Açıklamadan çıkarılan her iddia, aşağıdaki adlandırılmış
# regex kalıplarından birinin eşleşmesidir; her çelişki de kullanıcının forma
# girdiği veri ile o iddianın karşılaştırılmasıdır. Aynı metin her zaman aynı
# sonucu verir, "model bugün böyle yorumladı" durumu yoktur.

_CLAIM_PATTERNS: list[tuple[str, str, str]] = [
    # (anahtar, insan-okur etiket, regex)
    ("hasarsiz",    "Hasarsız / kaza kaydı yok",
     r"hasars[ıi]z|(hasar|kaza|tramer) kayd[ıi] (yok|bulunmamaktad[ıi]r|bulunmuyor)|tramersiz|tramer[ıi]? (yok|s[ıi]f[ıi]r)"),
    ("boyasiz",     "Boyasız",
     r"boyas[ıi]z|boya yok|hi[çc] boya|boyal[ıi] de[ğg]il"),
    ("degisensiz",  "Değişensiz",
     r"de[ğg]i[şs]ensiz|de[ğg]i[şs]en (yok|bulunmamaktad[ıi]r)|de[ğg]i[şs]eni yok"),
    ("hatasiz",     "Hatasız / kusursuz",
     r"hatas[ıi]z|kusursuz|s[ıi]f[ıi]r ayar[ıi]nda|s[ıi]f[ıi]r gibi"),
    ("agir_hasar",  "Ağır hasar / pert kaydı",
     # NOT: "pert" kelimesi \b (kelime sınırı) OLMADAN yazılırsa "eks-PERT-iz"
     # / "ex-PERT-iz" içindeki alt-diziyle eşleşir -- 791 ilanlık örneklemde
     # bu tek eksik \b, ilanların %43'ünü yanlışlıkla "ağır hasar" olarak
     # işaretliyordu (gerçek oran %6). Asla \b'siz yazma.
     r"a[ğg][ıi]r hasar|\bpert\b|hasar kay[ıi]tl[ıi]|[çc]ekme belge"),
    ("bakimli",     "Bakımları yapılmış",
     r"bak[ıi]ml[ıi]|bak[ıi]mlar[ıi] (yap[ıi]lm[ıi][şs]|tam|yeni)|yetkili serviste|periyodik bak[ıi]m"),
    ("tek_el",      "Tek elden / ilk sahibinden",
     r"tek el|ilk sahibinden|tek sahibinden|babadan kalma|ilk sahibi"),
    ("garanti",     "Garantisi devam ediyor",
     r"garantisi (devam|s[üu]r[üu]yor)|garanti kapsam[ıi]nda|fabrika garantili"),
    ("masrafsiz",   "Masrafsız",
     r"masrafs[ıi]z|masraf[ıi] yok|hi[çc]bir masraf"),
    ("takas",       "Takas kabul ediyor",
     r"takas (olur|yap[ıi]l[ıi]r|kabul)|takasa a[çc][ıi]k|takasl[ıi]"),
    ("kredi",       "Kredi / senet imkânı",
     r"kredi imkan|kredili|senetli|vade|taksit"),
    ("degisen_var", "Metinde değişen parçadan söz ediliyor",
     r"\d+\s*(par[çc]a|adet)?\s*de[ğg]i[şs]|de[ğg]i[şs]en(i)? (var|mevcut)"),
    ("boya_var",    "Metinde boyadan söz ediliyor",
     r"\d+\s*(par[çc]a|adet)?\s*boyal[ıi]|lokal boya|boyas[ıi] var"),
    ("ekspertiz",   "Ekspertiz raporu var",
     r"ekspertiz(li| rapor)"),
    ("acil",        "Acil satış vurgusu",
     r"acil|kelepir|f[ıi]rsat ka[çc]maz|pi[şs]man olmazs[ıi]n[ıi]z"),
    ("pazarlik_yok","Pazarlık payı yok deniyor",
     r"pazarl[ıi]k yok|tek fiyat|son fiyat"),
    ("ticari",      "Ticari / filo kullanımı",
     r"ticari kullan|filo|kiral[ıi]k|rent a car|[şs]irket ad[ıi]na"),
    ("faturali",    "Faturalı / maliye kayıtlı",
     r"\bfaturas[ıi]\s*(var|mevcut)|\bfatural[ıi]\b"),
    ("yetki_belge", "Yetkili galeri belgesi paylaşılmış",
     r"yetki belge(si)?\s*(no)?\s*[:.]?\s*\d"),
    ("muayene",     "Muayene bilgisi paylaşılmış",
     r"muayene(si)?\s*(bitiş|tarihi|durumu)?"),
    ("kasko",       "Kasko değeri paylaşılmış",
     r"kasko\s*(kodu|de[ğg]eri)?\s*[:.]?\s*\d"),
    ("yedek_anahtar", "Yedek anahtar bilgisi var",
     r"yedek anahtar[ıi]?\s*(mevcut|var)"),
    ("minimizing",  "Olumsuz bilgi 'sadece/yalnızca' ile küçümsenmiş",
     r"(sadece|yaln[ıi]zca)\s*(\d+\s*(par[çc]a|adet)?\s*)?(boya|de[ğg]i[şs])"),
]

# Galeri ilanlarının kalıp gibi tekrar ettiği "biz böyle araç almayız/satmayız"
# cümleleri: bir claim regex'i (özellikle agir_hasar/degisen_var/boya_var)
# aracın KENDİ durumuyla değil, galerinin genel satış politikasıyla eşleşmiş
# olabilir. 791 ilanlık örneklemde bu, potansiyel çelişki adaylarının
# %76'sını (17'de 13) oluşturuyordu -- cümle bazlı bu filtre olmadan
# kullanıcıya sahte "çelişki" uyarısı gösterilir.
_POLICY_SENTENCE = re.compile(
    r"(almay[ıi]z|satmay[ıi]z|almamaktad[ıi]r|satmamaktad[ıi]r|"
    r"al[ıi]p satm[ıi]yoruz|yap[ıi]lmamaktad[ıi]r|yapmamaktad[ıi]r|"
    r"al[ıi]nmaz|sat[ıi]lmaz|takas(a)? almamaktad[ıi]r|"
    r"al[ıi]m ve sat[ıi]m[ıi]n[ıi] yapm[ıi]yoruz|"
    r"ile ([çc]al[ıi][şs]m[ıi]yoruz|ilgilenmiyoruz)|"
    r"arac[ıi]?(lar[ıi])? (ile|ilgilenmiyoruz))",
    re.I,
)

_KM_IN_TEXT = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+|\d{4,7})\s*(?:bin\s*)?km", re.I)

# "TRAMER 7500₺", "HASAR KAYDI 8.000 TL'DİR", "1.300 TL HASAR KAYDI VARDIR"
# gibi ifadelerden somut TL tutarını çıkarır -- formdaki hasar/tramer
# bilgisiyle büyüklük mertebesi karşılaştırması için.
_TRAMER_AMOUNT = re.compile(
    r"(?:tramer|hasar)[^.\n]{0,20}?(\d{1,3}(?:[.\s]\d{3})*)\s*(?:tl|₺)"
    r"|(\d{1,3}(?:[.\s]\d{3})*)\s*(?:tl|₺)[^.\n]{0,20}?(?:tramer|hasar)",
    re.I,
)

# Yapılandırılmış ekspertiz bloğu: "BOYA: ...", "DEĞİŞEN: ...", "TRAMER
# BİLGİSİ: ..." gibi satır-bazlı key:value ifadeler. Bu format serbest metne
# göre çok daha güvenilir -- 791 ilanlık örneklemde ilanların %43'ü
# EKSPERTİZ/EXPERTİZ kelimesi geçen böyle bir blok içeriyordu.
_EXPERTISE_LINE = re.compile(
    r"^\s*(boya|de[ğg]i[şs]en|tramer(\s*bilgisi)?|hasar\s*kayd[ıi])\s*[:\-]\s*(.+)$",
    re.I | re.M,
)

# Kredi/taksit/telefon/adres gibi araçla ilgisi olmayan "gürültü" satırları --
# açıklamanın ne kadarının gerçekten araç bilgisi taşıdığını ölçmek için.
_NOISE_PATTERNS = re.compile(
    r"kredi|taksit|senet|vade|pe[şs]inat|0\s?5\d{2}[\s.\-]?\d{3}|"
    r"whatsapp|showroom|plaza|şube|bay[ıi]i|iletişim|telefon",
    re.I,
)

# ── Yapısal / güvenlik-kritik bileşenler ────────────────────────────────────
# Form'daki damage listesi sadece "parça değişti/boyalı" düzeyinde soru
# sorar; şase/podye/direk/airbag/motor/sandık gibi taşıyıcı-gövde ve
# güvenlik sistemi bilgisi HİÇ formda yok. Bu yüzden bu bileşenler hakkında
# açıklamada geçen bilgi, form ile karşılaştırılamaz -- ama tek başına çok
# güçlü bir sinyaldir (pozitif ya da negatif). 791 ilanlık örneklemde bu
# kelimeler neredeyse hep POZİTİF garanti cümlesi olarak geçiyordu
# ("ŞASE PODYE AİRBAG ORJİNALDİR" gibi) -- gerçek negatif itiraf çok
# nadir ama göründüğünde en ağır sinyaldir.
#
# Her bileşen kategorisi için: kelime geçen cümle _NEGATIVE_INDICATOR
# taşıyorsa VE _STRUCTURAL_NEGATION (yok/değil/kesinlikle... vb) taşımıyorsa
# "confirmed negatif" sayılır. Aksi halde (pozitif kelime veya negation'lı
# olumsuzlama varsa) "confirmed pozitif/temiz" sayılır.
_STRUCTURAL_COMPONENTS: list[tuple[str, str, float]] = [
    # (key, kelime regex'i, negatif sinyalin fiyat etkisi %)
    ("sase_podye_direk", r"\b[şs]ase\b|\b[şs]asi\b|\bpodye\b|\bdirek\b", -15.0),
    ("airbag_acmis",     r"airbag|hava\s*yast[ıi][ğg][ıi]",              -10.0),
    ("motor_degisti",    r"motor\s*(de[ğg]i[şs](ti|mi[şs])|komple\s*(yenilendi|de[ğg]i[şs]))", -6.0),
    ("sandik_bagaj",     r"\bsand[ıi]k\b|bagaj\s*havuzu",                 -5.0),
]

_STRUCTURAL_POSITIVE = re.compile(
    r"orjinal|orijinal|i[şs]lemsiz|hatas[ıi]z(d[ıi]r)?|sa[ğg]lam|har[ıi][çc]|temiz\b", re.I,
)
_STRUCTURAL_DAMAGE_WORD = re.compile(
    r"hasar|kaynak(l[ıi])?|k[ıi]r[ıi]k|ezik|i[şs]lem\s*(var|mevcut|g[öo]r(m[üu][şs])?)|"
    r"de[ğg]i[şs](mi[şs]|ti|en)|a[çc]m[ıi][şs]|patlam[ıi][şs]|oynanm[ıi][şs]|oynama",
    re.I,
)
# NOT: "hatasız" _STRUCTURAL_POSITIVE'e taşındı (önceden sadece negation'da
# vardı ve "1 DEĞİŞEN KAPUT HARİÇ HATASIZ ŞASE PODYE AİRBAG TEMİZ" gibi asıl
# POZİTİF garanti cümlelerini negatif işaretliyordu). Ayrıca pasif çatı
# "satılmamaktadır/alınmamaktadır" eksikti -- galeri politika cümlesi
# "...tarafımızca alınıp satılmamaktadır" bu yüzden negatif kaçıyordu; artık
# _POLICY_SENTENCE ile aynı cümle bazlı filtre burada da uygulanıyor.
_STRUCTURAL_NEGATION = re.compile(
    r"yok(tur)?|bulunmam|kesinlikle|de[ğg]il|olmayan|s[öo]z\s*konusu\s*(bile\s*)?de[ğg]il|"
    r"almamaktad[ıi]r|satmamaktad[ıi]r|al[ıi]nmamaktad[ıi]r|sat[ıi]lmamaktad[ıi]r|"
    r"almay[ıi]z|satmay[ıi]z",
    re.I,
)


# Sadece aracın kendi durumunu değil, galerinin genel politikasını da
# anlatabilecek claim'ler -- bunlar için eşleşen ifadenin cümlesi ayrıca
# _POLICY_SENTENCE'a karşı kontrol edilir.
_POLICY_SENSITIVE_CLAIMS = {"agir_hasar", "degisen_var", "boya_var", "hasarsiz"}


def _sentence_around(text: str, start: int, end: int) -> str:
    """Eşleşmenin bulunduğu tam cümleyi (önceki/sonraki nokta veya satır
    sonuna kadar) döndürür -- kelime bazlı bağlam yerine cümle bazlı."""
    left = max(text.rfind("\n", 0, start), text.rfind(".", 0, start))
    right_candidates = [x for x in (text.find("\n", end), text.find(".", end)) if x != -1]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1:right + 1].strip()


def _is_policy_sentence(text: str, pattern: str) -> bool:
    """Verilen pattern'in eşleştiği HER cümle galeri-politikası mı (yani
    aracın kendi durumuyla değil, galerinin genel satın alma/satış
    kurallarıyla ilgili mi)? Hepsi politika cümlesiyse True -- bu durumda
    claim aracın kendisine ait bir iddia sayılmaz."""
    matches = list(re.finditer(pattern, text, re.I))
    if not matches:
        return False
    for m in matches:
        sentence = _sentence_around(text, m.start(), m.end())
        if not _POLICY_SENTENCE.search(sentence):
            return False
    return True


def _detect_claims(text: str) -> dict[str, str]:
    """Metinde geçen iddialar. Anahtar -> etiket.

    Politikaya-duyarlı claim'lerde (agir_hasar, degisen_var, boya_var,
    hasarsiz) tüm eşleşmeler galeri politikası cümlesiyse ("ağır hasarlı
    araç almayız" gibi) claim eklenmez -- aracın kendi durumuyla ilgisi yok.
    """
    low = _norm(text)
    found: dict[str, str] = {}
    for key, label, pattern in _CLAIM_PATTERNS:
        if not re.search(pattern, low):
            continue
        if key in _POLICY_SENSITIVE_CLAIMS and _is_policy_sentence(low, pattern):
            continue
        found[key] = label
    return found


# "hasar_kaydı" / "hasar_kaydi" gibi tek harf (ı/i) farklı yazılan aynı
# kavramı tek kanonik anahtara indirger -- yoksa aynı bilgi farklı ilanlarda
# iki ayrı sözlük anahtarı olarak görünür.
_EXPERTISE_KEY_CANON = {
    "hasar_kaydı": "hasar_kaydi",
    "tramer_bilgisi": "tramer",
    "değişen": "degisen",
    "deği̇şen": "degisen",
    "degişen": "degisen",
}


def _extract_expertise_block(text: str) -> dict[str, str]:
    """Yapılandırılmış 'BOYA: ...', 'DEĞİŞEN: ...', 'TRAMER: ...' satırlarını
    çıkarır. Serbest metin regex'inden çok daha güvenilir -- galeri kendi
    ekspertiz özetini bu formatta yazdıysa öncelikli veri kaynağıdır."""
    out: dict[str, str] = {}
    for m in _EXPERTISE_LINE.finditer(text):
        # NFC normalize + "İ".lower()'ın ürettiği "i̇" (i + combining dot)
        # dizisini düz "i"ye indirger -- yoksa anahtar adları "deği̇şen" gibi
        # görünmez birleşik karakter taşır.
        key = unicodedata.normalize("NFC", _norm(m.group(1))).replace("i̇", "i").replace(" ", "_")
        key = _EXPERTISE_KEY_CANON.get(key, key)
        value = m.group(3).strip()
        if value:
            out[key] = value
    return out


def _extract_tramer_amount(text: str) -> int | None:
    """Metindeki ilk tramer/hasar TL tutarını sayıya çevirir (varsa)."""
    m = _TRAMER_AMOUNT.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    digits = re.sub(r"[.\s]", "", raw or "")
    try:
        value = int(digits)
    except ValueError:
        return None
    return value if 0 < value < 10_000_000 else None


def _structural_findings(text: str) -> dict[str, list[dict]]:
    """Şase/podye/direk/airbag/motor/sandık gibi form-dışı yapısal
    bileşenler hakkında açıklamada geçen sinyalleri toplar.

    Döner: {"negative": [{"key","sentence","pct"}], "positive": [{"key","sentence"}]}
    Aynı bileşen birden fazla cümlede geçebilir -- her cümle ayrı
    değerlendirilir (biri pozitif biri negatif olabilir, ör. "1 değişen
    kaput hariç şase podye orijinal" gibi karma ilanlar için)."""
    negative: list[dict] = []
    positive: list[dict] = []
    for key, word_pattern, pct in _STRUCTURAL_COMPONENTS:
        seen_sentences: set[str] = set()
        for m in re.finditer(word_pattern, text, re.I):
            sentence = _sentence_around(text, m.start(), m.end())
            if sentence in seen_sentences:
                continue
            seen_sentences.add(sentence)
            has_damage_word = bool(_STRUCTURAL_DAMAGE_WORD.search(sentence))
            has_negation = bool(_STRUCTURAL_NEGATION.search(sentence))
            has_positive_word = bool(_STRUCTURAL_POSITIVE.search(sentence))
            is_policy = bool(_POLICY_SENTENCE.search(sentence))
            if has_damage_word and not has_negation and not has_positive_word and not is_policy:
                negative.append({"key": key, "sentence": sentence, "pct": pct})
            elif has_positive_word or has_negation or is_policy:
                positive.append({"key": key, "sentence": sentence})
    return {"negative": negative, "positive": positive}


def _noise_ratio(text: str) -> float:
    """Açıklamanın kredi/taksit/telefon/adres gibi araçla ilgisiz 'gürültü'
    satırlarının oranı. 1.0'a yakınsa açıklama araç bilgisi taşımıyor
    demektir."""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return 0.0
    noisy = sum(1 for ln in lines if _NOISE_PATTERNS.search(ln))
    return noisy / len(lines)


def _km_claims(text: str) -> list[int]:
    out: list[int] = []
    for raw in _KM_IN_TEXT.findall(text or ""):
        digits = re.sub(r"[.\s]", "", raw)
        try:
            value = int(digits)
        except ValueError:
            continue
        if 1_000 <= value <= 2_000_000:
            out.append(value)
    return out


# Toplam fiyat etkisi bu sınırların dışına çıkamaz. Negatif tavan çok daha
# geniş tutuldu çünkü "ilanda yalan/eksik bilgi olma" riski, "iyi bakılmış
# olma" ihtimalinden çok daha maliyetli bir hatadır -- galeriler zaten
# hemen hep olumlu yazar, pozitif tarafta abartıya izin vermemek gerekir.
_IMPACT_CAP_NEGATIVE = -20.0
_IMPACT_CAP_POSITIVE = 6.0


def _compute_price_impact(events: list[tuple[str, str, float]], price: int | None) -> dict | None:
    """Açıklamadan çıkan sinyalleri tek bir yüzdelik fiyat etkisine indirger.

    `price` verilmediyse (örn. B2C formu henüz fiyat girmemiş) sadece
    kuralları ve toplam yüzdeyi döner, TL tutarı hesaplamaz."""
    if not events:
        return {
            "total_pct": 0.0, "rules": [], "base_price": price,
            "adjusted_price": price, "delta": 0 if price is not None else None,
        }

    rules = [{"key": k, "label": label, "pct": pct} for k, label, pct in events]
    neg_sum = sum(pct for _, _, pct in events if pct < 0)
    pos_sum = sum(pct for _, _, pct in events if pct > 0)
    neg_capped = max(neg_sum, _IMPACT_CAP_NEGATIVE)
    pos_capped = min(pos_sum, _IMPACT_CAP_POSITIVE)
    total_pct = round(neg_capped + pos_capped, 1)

    adjusted_price = None
    delta = None
    if price is not None and price > 0:
        adjusted_price = round(price * (1 + total_pct / 100))
        delta = adjusted_price - price

    return {
        "total_pct": total_pct,
        "rules": rules,
        "base_price": price,
        "adjusted_price": adjusted_price,
        "delta": delta,
    }


def description_insights(description: str, *, damage: list, agir_hasar: bool,
                         km: float, year: int, price: int | None = None) -> dict:
    """İlan açıklamasından anlam çıkarımı.

    En değerli çıktı `contradictions`: metindeki iddia ile kullanıcının forma
    girdiği veri çakışıyorsa (ör. "değişensiz" yazıyor ama 3 parça değişmiş
    işaretli) bu, ilanda bilerek ya da bilmeyerek yanlış bilgi olduğunun
    somut göstergesidir ve pazarlıkta doğrudan koz olur.

    `price` verilirse `price_impact` alanı da hesaplanır: açıklamadaki
    sinyallere göre form-tahminine göre ayrı bir "açıklamaya göre düzeltilmiş
    fiyat" üretilir (bkz. _IMPACT_CAP_NEGATIVE / _IMPACT_CAP_POSITIVE).
    """
    from .description_quality import score_description

    if not (description or "").strip():
        return {
            "available": False,
            "score": 0,
            "label": "Açıklama girilmedi",
            "summary": "İlan açıklaması girilmediği için metin analizi yapılamadı.",
            "claims": [], "contradictions": [], "red_flags": [],
            "positives": [], "missing": [], "km_claims": [],
            "expertise_block": {}, "tramer_amount": None, "noise_ratio": 0.0,
            "price_impact": None,
        }

    text = description.strip()
    # Fiyat etkisi kuralları burada birikir: (anahtar, insan-okur etiket, %).
    # Aynı anahtar iki kez eklenmez (bkz. _add_impact).
    impact_events: list[tuple[str, str, float]] = []
    _impact_seen: set[str] = set()

    def _add_impact(key: str, label: str, pct: float) -> None:
        if key in _impact_seen:
            return
        _impact_seen.add(key)
        impact_events.append((key, label, pct))

    base = score_description(text)
    claims = _detect_claims(text)
    expertise_block = _extract_expertise_block(text)
    tramer_amount = _extract_tramer_amount(text)
    noise_ratio = round(_noise_ratio(text), 2)
    structural = _structural_findings(text)

    changed = [d for d in damage if "değiş" in _norm(d.get("durum"))]
    painted = [d for d in damage if "boya" in _norm(d.get("durum"))]

    contradictions: list[dict] = []

    def clash(claim_key: str, detail: str) -> None:
        if claim_key in claims:
            contradictions.append({"claim": claims[claim_key], "conflict": detail})

    if changed:
        clash("degisensiz", f"Formda {len(changed)} parça değişmiş olarak işaretli.")
        clash("hasarsiz", f"Formda {len(changed)} parça değişmiş olarak işaretli.")
        clash("hatasiz", f"Formda {len(changed)} parça değişmiş olarak işaretli.")
    if painted:
        clash("boyasiz", f"Formda {len(painted)} parça boyalı olarak işaretli.")
        clash("hatasiz", f"Formda {len(painted)} parça boyalı olarak işaretli.")
    if agir_hasar:
        clash("hasarsiz", "Formda ağır hasar kaydı var olarak işaretli.")
        clash("hatasiz", "Formda ağır hasar kaydı var olarak işaretli.")
    if not damage and not agir_hasar:
        if "degisen_var" in claims:
            contradictions.append({
                "claim": claims["degisen_var"],
                "conflict": "Formda hiçbir parça değişmiş işaretlenmemiş — hasar bilgisi eksik girilmiş olabilir.",
            })
            _add_impact("degisen_var", "Formda yok ama açıklamada değişen parça iddiası var", -3.0)
        if "boya_var" in claims:
            contradictions.append({
                "claim": claims["boya_var"],
                "conflict": "Formda hiçbir parça boyalı işaretlenmemiş — hasar bilgisi eksik girilmiş olabilir.",
            })
            _add_impact("boya_var", "Formda yok ama açıklamada boyalı parça iddiası var", -2.0)

    # Aynı iddia birden çok kuralla çakışabiliyor ("Hatasız" hem değişen hem
    # boya ile) -- kullanıcıya tek satır olarak, gerekçeleri birleştirilmiş
    # halde gösterilir.
    merged: dict[str, list[str]] = {}
    for item in contradictions:
        merged.setdefault(item["claim"], [])
        if item["conflict"] not in merged[item["claim"]]:
            merged[item["claim"]].append(item["conflict"])
    contradictions = [
        {"claim": claim, "conflict": " ".join(conflicts)}
        for claim, conflicts in merged.items()
    ]

    # Metindeki km beyanı ile forma girilen km tutuyor mu?
    km_claims = _km_claims(text)
    for claimed in km_claims:
        if km and abs(claimed - km) / max(km, 1) > 0.15:
            contradictions.append({
                "claim": f"Açıklamada {claimed:,} km yazıyor".replace(",", "."),
                "conflict": f"Forma {int(km):,} km girildi — aradaki fark %15'ten fazla.".replace(",", "."),
            })
            _add_impact("km_contradiction", "Açıklama km'si form km'siyle %15'ten fazla farklı", -4.0)
            break

    red_flags = list(base.get("negatives") or [])
    if "acil" in claims:
        red_flags.append("Acil satış vurgusu var — aceleye getirilen satışlarda kusur saklama riski yüksektir.")
        _add_impact("acil", "Acil satış vurgusu", -2.0)
    if "pazarlik_yok" in claims:
        red_flags.append("İlan pazarlık payı olmadığını söylüyor; teklif stratejinizi buna göre kurun.")
    if "ticari" in claims:
        red_flags.append("Ticari/filo kullanım işareti var — bu araçlar aynı yaş ve km'de daha yıpranmış olur.")
        _add_impact("ticari", "Ticari/filo kullanım işareti", -3.0)
    if "minimizing" in claims:
        red_flags.append(
            "Açıklamada olumsuz bilgi 'sadece/yalnızca' ile küçümsenerek verilmiş — "
            "gerçek boyutunu satıcıya doğrudan sorun."
        )
        _add_impact("minimizing", "Olumsuz bilgi 'sadece/yalnızca' ile küçümsenmiş", -3.0)
    if "agir_hasar" in claims and not agir_hasar:
        red_flags.append("Açıklamada ağır hasar/pert ifadesi geçiyor ama formda işaretlenmemiş.")
        _add_impact("agir_hasar_contradiction", "Formda yok ama açıklamada ağır hasar/pert iddiası var", -8.0)
    if tramer_amount is not None and tramer_amount >= 50_000:
        red_flags.append(
            f"Açıklamada {tramer_amount:,} TL tramer/hasar kaydı geçiyor — bu, küçük bir "
            "tramerin çok ötesinde bir tutar; ekspertiz şart.".replace(",", ".")
        )
        _add_impact("tramer_high", f"Yüksek tramer/hasar tutarı ({tramer_amount:,} TL)".replace(",", "."), -5.0)
    elif tramer_amount is not None and tramer_amount >= 15_000:
        _add_impact("tramer_mid", f"Orta düzey tramer/hasar tutarı ({tramer_amount:,} TL)".replace(",", "."), -2.0)
    if noise_ratio >= 0.6:
        red_flags.append(
            "Açıklamanın büyük bölümü kredi/taksit/iletişim bilgisi — araç hakkında "
            "somut bilgi az; satıcıyı arayıp teyit etmeniz gerekir."
        )
        _add_impact("noise_ratio", "Açıklamanın çoğu kredi/taksit/iletişim bilgisi, araç bilgisi az", -1.0)

    # Yapısal/güvenlik-kritik bileşenler (form dışı): en ağır negatif sinyal.
    for finding in structural["negative"]:
        pct = finding["pct"]
        label_map = {
            "sase_podye_direk": "Şase/podye/direkte hasar veya işlem izi",
            "airbag_acmis": "Airbag açmış/patlamış",
            "motor_degisti": "Motor değişmiş/komple yenilenmiş",
            "sandik_bagaj": "Sandık/bagaj havuzunda hasar",
        }
        label = label_map.get(finding["key"], finding["key"])
        red_flags.append(
            f"{label} — açıklamada geçiyor ('{finding['sentence'][:80]}'). "
            "Bu form dışı, ekstra bir bulgu; mutlaka ekspertiz yaptırın."
        )
        _add_impact(finding["key"], label, pct)
    if structural["positive"] and not structural["negative"]:
        _add_impact(
            "structural_clean",
            "Şase/podye/airbag gibi kritik bölgeler 'orijinal/işlemsiz' olarak garanti edilmiş",
            1.5,
        )

    positives = list(base.get("positives") or [])
    for key, pct in (
        ("garanti", 2.0), ("tek_el", 1.5), ("faturali", 1.0), ("ekspertiz", 1.0),
        ("masrafsiz", 1.0), ("bakimli", 1.0),
    ):
        if key in claims:
            positives.append(claims[key])
            _add_impact(key, claims[key], pct)
    for key in ("yetki_belge", "muayene", "kasko", "yedek_anahtar"):
        if key in claims:
            positives.append(claims[key])
            _add_impact(key, claims[key], 0.5)
    if tramer_amount is not None and tramer_amount < 15_000:
        positives.append(f"Tramer/hasar kaydı düşük tutarlı ({tramer_amount:,} TL).".replace(",", "."))
        _add_impact("tramer_low", f"Düşük tutarlı tramer/hasar kaydı ({tramer_amount:,} TL)".replace(",", "."), 1.0)

    # Açıklamada HİÇ değinilmemiş kritik konular -> "satıcıya sorun" beslemesi
    missing: list[str] = []
    if not any(k in claims for k in ("hasarsiz", "degisensiz", "boyasiz", "degisen_var", "boya_var", "ekspertiz")):
        missing.append("Hasar / tramer / boya-değişen durumu")
    if "bakimli" not in claims:
        missing.append("Bakım geçmişi")
    if "tek_el" not in claims:
        missing.append("Aracın kaç farklı sahibi olduğu")
    # Garanti sorusu yalnızca hâlâ garantide OLABİLECEK araçlarda anlamlı:
    # 2 yaşından büyük ya da 100.000 km üstü araçta fabrika garantisi bitmiştir.
    vehicle_age = max(0, datetime.now().year - int(year))
    if "garanti" not in claims and vehicle_age <= 2 and km <= 100_000:
        missing.append("Garanti durumu")

    # Puan: description_quality'nin 1-10'u, çelişki başına -2.
    score = int(max(1, min(10, (base.get("score") or 1) - 2 * len(contradictions))))
    if contradictions:
        label = "Çelişkili — dikkat"
    elif score >= 8:
        label = "Açıklama güçlü ve şeffaf"
    elif score >= 5:
        label = "Açıklama yeterli"
    else:
        label = "Açıklama zayıf"

    if contradictions:
        summary = (
            f"Açıklamada {len(contradictions)} adet, girdiğiniz araç bilgisiyle "
            "çelişen ifade bulundu. Bu maddeleri satıcıya doğrudan sorun — "
            "pazarlıkta en güçlü kozunuz bunlar."
        )
    elif not missing:
        summary = "Açıklama kritik konuların tamamına değinmiş; bilgi eksiği görünmüyor."
    else:
        summary = (
            "Açıklama şu konulara hiç değinmemiş: " + ", ".join(missing).lower() + "."
        )

    price_impact = _compute_price_impact(impact_events, price)

    return {
        "available": True,
        "score": score,
        "label": label,
        "summary": summary,
        "claims": [{"key": k, "label": v} for k, v in claims.items()],
        "contradictions": contradictions,
        "red_flags": red_flags,
        "positives": positives,
        "missing": missing,
        "km_claims": km_claims,
        "suggestions": base.get("suggestions") or [],
        "expertise_block": expertise_block,
        "tramer_amount": tramer_amount,
        "noise_ratio": noise_ratio,
        "price_impact": price_impact,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5) Güncel benzer ilanlar
# ═══════════════════════════════════════════════════════════════════════════

def _km_int(raw: Any) -> int | None:
    """galeri_latest_snapshot.json'daki km zaten build script'inde temizlenmiş
    sayısal değer (bkz. scripts/build_galeri_summary.py:parse_km) — burada sadece
    tam sayıya çevrilip saçma yüksek değerler (1.5M üstü) elenir."""
    if raw is None:
        return None
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return None
    return value if 0 < value <= 1_500_000 else None


@lru_cache(maxsize=256)
def _similar_rows(brand: str, series: str, year_lo: int, year_hi: int, _version: str) -> tuple:
    brand_key, series_key = _norm(brand), _norm(series)
    rows = [
        row for row in galeri_summary.latest_snapshot().get("listings", [])
        if _norm(row.get("brand")) == brand_key and _norm(row.get("series")) == series_key
        and row.get("year") is not None and year_lo <= row["year"] <= year_hi
        and row.get("price") is not None and _MIN_REAL_PRICE <= row["price"] <= _MAX_REAL_PRICE
    ]
    rows.sort(key=lambda r: r["price"])
    return tuple(rows[:400])


def similar_listings(brand: str, series: str, year: int, price: int | None,
                     limit: int = 12) -> list[dict]:
    """Şu anda YAYINDA olan benzer ilanlar — galeri_latest_snapshot.json'daki
    en son güne ait ilanlardan (bkz. scripts/build_galeri_summary.py).

    B2B tarafındaki "Yayındaki Benzer İlanları Bul" arabam.com'a canlı istek
    atıyor ve production IP'si 403 yiyor (bkz. README). B2C'de o yola hiç
    girilmiyor: veri zaten günlük üretilen özet JSON'dan okunuyor, hem anında
    hem de engellenemez.
    """
    try:
        rows = _similar_rows(brand, series, year - _YEAR_TOLERANCE, year + _YEAR_TOLERANCE,
                             _data_version())
    except Exception:
        return []

    out: list[dict] = []
    for row in rows:
        listing_price = int(row["price"])
        out.append({
            "title": (row.get("title") or f"{row.get('brand', '')} {row.get('series', '')}".strip()),
            "model": f"{row.get('brand', '')} {row.get('series', '')}".strip(),
            "year": row.get("year"),
            "km": _km_int(row.get("km")),
            "color": (row.get("color") or "").strip() or None,
            "price": listing_price,
            "url": row.get("url") or None,
            "gallery": (row.get("gallery") or "").strip() or None,
            "city": (row.get("city") or "").strip() or None,
            "district": (row.get("district") or "").strip() or None,
            "post_age_days": row.get("post_age_days"),
            "price_diff": (listing_price - price) if price else None,
        })

    # En ucuzdan değil, KULLANICININ İLANINA en yakınlardan başlayarak seç --
    # amaç "en ucuz araba" listesi değil, gerçek emsal karşılaştırması.
    if price:
        out.sort(key=lambda r: abs(r["price"] - price))
    return out[:limit]
