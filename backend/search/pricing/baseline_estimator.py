"""
baseline_estimator.py
=====================
Pure-logic pricing engine using paket_fiyatlari.json / paket_fiyatlari_suv.json.

Usage:
    from baseline_estimator import estimate_price, load_paket_baseline

    paket_db = load_paket_baseline()
    est = estimate_price(
            brand="fiat", series="egea",
            model="1.6 Multijet Easy",
            year=2020, listing_km=90_000,
            damage=[
                {"parca": "Sol Ön Kapı", "durum": "Boyalı"},
                {"parca": "Çamurluk",    "durum": "Değişmiş"},
            ],
            paket_db=paket_db)
    # -> {"tahmini_fiyat": ..., "km_factor": ..., "damage_factor": ...,
    #    "base_price": ..., "level": "paket", "found": True, ...}

Lookup:
    paket_fiyatlari (marka-seri-motor[-paket] slug) -- tek kaynak.
    - paket_fiyatlari.json / paket_fiyatlari_suv.json'dan gelir.
    - Yil bazli bucket yoktur (tek anlik "en dusuk km'den ilk 5" referansi),
      bu yuzden yil farkina gore amortisman orani ile ekstrapole edilir.
    - Guvenilirlik korumasi: MIN_PAKET_SAMPLES'tan az orneklem varsa
      kullanilmaz -- eslesme yok sayilir (found: False). Yil farki artik
      sinirlanmiyor (kaldirildi); ne kadar eski/yeni olursa olsun
      PAKET_DEPRECIATION_RATE ile ekstrapole edilir.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

# --- Constants --------------------------------------------------------------

_HERE = Path(__file__).parent

# 2026-08-14: Tek fiyat kaynagi artik SQLite (paket_fiyatlari.db) --
# bkz. db_ortak.py. Eskiden paket_fiyatlari*.json dosyalari okunuyordu;
# uzun/kesintiye ugrayan taramalarda bozulma riski tasidiklari icin DB'ye
# gecildi. load_paket_baseline() DB'den okuyup ayni "merged" dict
# formatinda dondurmeye devam eder -- bu modulun disina (central_price_
# estimator.py) hicbir arayuz degisikligi yansimaz.
_CATEGORY_MAP = {
    "otomobil": "otomobil",
    "arazi-suv-pick-up": "arazi-suv-pick-up",
    "minivan-panelvan": "minivan-panelvan",
}
MIN_PAKET_SAMPLES     = 3      # bu kadar ilan ornegi olmadan paket seviyesine guvenme

# 2026-08-24: measure_calibration_full.py ile 649 marka+seri+motor grubu /
# 59.006 gercek satis kaydi uzerinde OLCULMUS marka/kategori bazli
# kalibrasyon carpani -- motorun paket-bazli tahmininin sistematik olarak
# ne kadar fazla/az tahmin ettigini duzeltir (bkz. _calibration_factor()).
# n<MIN_CALIBRATION_BRAND_N olan markalarda kategoriye, o da yoksa global
# fallback'e dusulur.
#
# Tablo su an STATIK (olcum anindaki bir fotograf). paket_fiyatlari.db
# veya search_soldvehiclerecord onemli olcude guncellenirse (yeni tarama,
# daha fazla satis kaydi) measure_calibration_full.py TEKRAR calistirilip
# bu sozluk elle guncellenmeli -- otomatik yeniden hesaplama YOK.
CALIBRATION_FACTORS = {
    "by_brand": {
        # marka_slug: (carpan, olcum_orneklem_sayisi)
        "jeep": (0.9553, 223), "ford": (0.9334, 5125), "nissan": (0.9648, 1506),
        "mercedes-benz": (0.9031, 1237), "skoda": (0.9466, 1407), "hyundai": (0.9759, 2455),
        "citroen": (0.9948, 1426), "bmw": (0.9309, 2326), "volkswagen": (0.9287, 5522),
        "dacia": (0.9577, 1250), "peugeot": (0.9786, 2639), "fiat": (0.9579, 3533),
        "opel": (0.9751, 3000), "toyota": (0.9423, 1850), "chevrolet": (0.8902, 276),
        "renault": (0.9578, 6368), "audi": (0.8966, 363), "kia": (0.9782, 736),
        "togg": (0.9891, 205), "volvo": (0.9567, 497), "mg": (0.9463, 153),
        "seat": (0.9808, 553), "chery": (1.0054, 447), "mitsubishi": (0.9647, 234),
        "honda": (0.9520, 1013), "tofas": (0.7841, 286), "mini": (0.9082, 102),
        "cupra": (0.9898, 133),
    },
    "by_category": {
        # n<100 olan markalarda (byd, porsche, land-rover, vs.) fallback.
        "otomobil": 0.9451, "arazi-suv-pick-up": 0.9774, "minivan-panelvan": 0.9238,
    },
    "global": 0.9549,  # hicbir marka/kategori eslesmezse son care fallback
}
MIN_CALIBRATION_BRAND_N = 100  # bu esigin altinda marka-ozel katsayiya guvenilmez, kategoriye dus


def _calibration_factor(marka_slug: str | None, category: str | None) -> float:
    """Olculmus (bkz. yukaridaki blok) marka -> kategori -> global sirasiyla
    kalibrasyon carpanini doner. Hicbiri yoksa 1.0 (duzeltme uygulanmaz)
    DEGIL, global fallback doner -- olcum gostermistir ki motor sistematik
    olarak fazla tahmin ediyor, duzeltmesiz birakmak daha yanlis olurdu."""
    slug = (marka_slug or "").strip().lower()
    brand_entry = CALIBRATION_FACTORS["by_brand"].get(slug)
    if brand_entry is not None:
        factor, n = brand_entry
        if n >= MIN_CALIBRATION_BRAND_N:
            return factor
    cat_factor = CALIBRATION_FACTORS["by_category"].get(category or "")
    if cat_factor is not None:
        return cat_factor
    return CALIBRATION_FACTORS["global"]


# _age_adjustment_factor icin kademeli amortisman oranlari: (ust_sinir, yillik_oran).
# Her bracket, bir onceki ust sinirdan kendi ust sinirina kadar olan yillari kendi
# oranindan gecirir (bkz. _age_adjustment_factor docstring'i). Son bracket'in
# ust_sinir'i None -- sinirsiz (8 yil ustu tum fark bu orandan hesaplanir).
AGE_DEPRECIATION_BRACKETS = (
    (3, 0.04),      # 0-3 yil: yillik %4
    (8, 0.025),     # 3-8 yil: yillik %2.5
    (None, 0.01),   # 8+ yil: yillik %1
)
# Geriye donuk uyumluluk icin (baska modul import ediyorsa): orta dilim orani.
PAKET_DEPRECIATION_RATE = 0.025

KM_FACTOR_MIN = 0.70
KM_FACTOR_MAX = 1.10
KM_STEP_PCT   = 0.0019  # ARTIK KULLANILMIYOR -- bkz. asagidaki KM_CURVE_POINTS notu

# Damage tier multipliers
CRITICAL = {"tavan", "motor kaputu"}
MAJOR    = {
    "sağ ön kapı",  "sol ön kapı",
    "sağ arka kapı", "sol arka kapı",
    "sag on kapi",  "sol on kapi",
    "sag arka kapi", "sol arka kapi",
}

DURUM_PENALTY = {
    "lokal boyalı": 0.005,
    "lokal boyali": 0.005,
    "boyalı":       0.01,
    "boyali":       0.01,
    "değişmiş":     0.025,
    "degismis":     0.025,
}
AGIR_HASAR_FLAT = 0.15

# CRITICAL (tavan, motor kaputu) disindaki her parca icin ceza tam
# uygulanir ama art arda eklenen her YENI kritik-olmayan boyali/degisen
# parca bir oncekine gore azalan agirlikla sayilir (en yuksek etkili parca
# tam agirlikla, ikincisi NON_CRITICAL_STACK_DECAY kadar, ucuncusu onun da
# NON_CRITICAL_STACK_DECAY kati kadar...). Kaput/tavan bu azalmadan
# etkilenmez, her zaman tam agirlikla sayilir.
NON_CRITICAL_STACK_DECAY = 0.6

# paket_fiyatlari.json / paket_fiyatlari_suv.json'daki referans ilanlar
# vites bilgisi ayrimi yapilmadan toplandigi icin otomatik vites kabul
# edilir. Girilen arac manuel vitesli ise ek sabit indirim uygulanir.
GEAR_MANUAL_PENALTY = 0.10

MIN_COUNT_TRUSTED = 5


def _is_manual_gear(gear: str | None) -> bool:
    if not gear:
        return False
    g = gear.lower().strip()
    return "manuel" in g or g == "manual"


# --- DB helpers --------------------------------------------------------------

def _slugify(text: str) -> str:
    """
    Serbest metni arabam.com URL slug formatina cevirir: Turkce/ozel
    karakterler ve bosluk disindaki her seyi (orn. "Mercedes - Benz" ->
    "mercedes-benz") tek bir tirege indirger. Paket anahtari brand+series+
    model birlestirilerek kuruldugu icin (paket_fiyatlari.json'daki leaf_slug
    ile birebir eslesmesi gerektigi icin) bu siki normalizasyon kullanilir.
    """
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _row_to_entry(leaf_row, varyant_rows: list) -> dict | None:
    """Bir 'leaves' satiri + o leaf'e ait varyant satirlarindan, en iyi
    (orneklem sayisi en yuksek) varyanti ust seviyeye tasiyan bir entry
    dict'i uretir -- eski JSON formatiyla (ortalama_fiyat, ortalama_km,
    vites_bazli, ...) birebir ayni sekle sahiptir. Hicbir varyantta gecerli
    fiyat yoksa None doner (eski "hata"/fiyatsiz kayit atlama davranisiyla
    ayni).

    2026-08-14: Eskiden bu fonksiyon kendi icinde "SELECT * FROM varyantlar
    WHERE leaf_id=?" calistiriyordu -- her leaf icin ayri sorgu (N+1 sorgu
    deseni, ~9848 leaf icin binlerce ayri sorgu). Artik cagiran taraf
    (load_paket_baseline) TEK bir JOIN sorgusuyla tum varyantlari cekip
    leaf_id'ye gore gruplayip buraya hazir liste olarak veriyor."""
    vites_bazli: dict = {}
    for row in varyant_rows:
        if row["hata"]:
            vites_bazli[row["gear_key"]] = {"hata": row["hata"], "url": row["url"]}
        elif not row["fiyat_ornek_sayisi"]:
            vites_bazli[row["gear_key"]] = None
        else:
            vites_bazli[row["gear_key"]] = {
                "ilan_sayisi": row["ilan_sayisi"],
                "ortalama_fiyat": row["ortalama_fiyat"],
                "ortalama_km": row["ortalama_km"],
                "ortalama_yil": row["ortalama_yil"],
                "fiyat_ornek_sayisi": row["fiyat_ornek_sayisi"],
                "km_ornek_sayisi": row["km_ornek_sayisi"],
                "yil_ornek_sayisi": row["yil_ornek_sayisi"],
                "url": row["url"],
            }

    candidates = [v for v in vites_bazli.values() if v and "hata" not in v]
    if not candidates:
        return None
    best = max(candidates, key=lambda v: v.get("fiyat_ornek_sayisi", 0))

    entry = {
        "marka_slug": leaf_row["marka_slug"], "marka_adi": leaf_row["marka_adi"],
        "seri_slug": leaf_row["seri_slug"], "seri_adi": leaf_row["seri_adi"],
        "motor_slug": leaf_row["motor_slug"], "motor_adi": leaf_row["motor_adi"],
        "paket_slug": leaf_row["paket_slug"], "paket_adi": leaf_row["paket_adi"],
        "url": leaf_row["url"],
        "vites_bazli": vites_bazli,
    }
    entry.update(best)
    return entry


def load_paket_baseline(db_path: str | Path | None = None) -> dict:
    """
    paket_fiyatlari.db'den (bkz. db_ortak.py) tum leaf'leri okuyup, eski
    JSON tabanli load_paket_baseline() ile AYNI "merged" dict formatinda
    dondurur -- lookup_paket()/estimate_from_paket() hicbir degisiklik
    gerektirmez. Fiyati olmayan (hicbir varyantinda gecerli ilan bulunamamis)
    kayitlar atlanir.

    Ayni anahtar (leaf_slug) iki kategoride de varsa (teorik olarak, capraz
    kategori durumu), orneklem sayisi (fiyat_ornek_sayisi) daha yuksek olan
    kazanir ve bir uyari basilir.
    """
    from .reference import get_connection

    conn = get_connection(db_path)
    try:
        merged: dict = {}

        for source_category in _CATEGORY_MAP.values():
            leaf_rows = conn.execute(
                "SELECT * FROM leaves WHERE category=?", (source_category,)
            ).fetchall()

            # Tek JOIN sorgusuyla bu kategorideki TUM varyantlari cek,
            # leaf_id'ye gore Python tarafinda grupla -- bkz. _row_to_entry
            # docstring'i.
            varyant_rows = conn.execute(
                """
                SELECT v.* FROM varyantlar v
                JOIN leaves l ON l.id = v.leaf_id
                WHERE l.category = ?
                """,
                (source_category,),
            ).fetchall()
            varyantlar_by_leaf: dict[int, list] = {}
            for row in varyant_rows:
                varyantlar_by_leaf.setdefault(row["leaf_id"], []).append(row)

            for leaf_row in leaf_rows:
                entry = _row_to_entry(leaf_row, varyantlar_by_leaf.get(leaf_row["id"], []))
                if entry is None:
                    continue

                key = leaf_row["leaf_slug"]
                entry["_category"] = source_category
                merged[f"{source_category}:{key}"] = entry

                display_model = " ".join(
                    part for part in (entry.get("motor_adi"), entry.get("paket_adi")) if part
                )
                if entry.get("marka_adi") and entry.get("seri_adi") and display_model:
                    display_key = _paket_key(
                        entry["marka_adi"], entry["seri_adi"], display_model
                    )
                    merged[f"{source_category}:{display_key}"] = entry

                if key in merged:
                    existing = merged[key]
                    if entry.get("fiyat_ornek_sayisi", 0) <= existing.get("fiyat_ornek_sayisi", 0):
                        continue
                    print(f"[baseline_estimator] UYARI: paket anahtari cakismasi '{key}' - "
                          f"daha fazla ornekli kayit kullanildi.")

                merged[key] = entry

        return merged
    finally:
        conn.close()


def _paket_key(brand: str, series: str, model: str) -> str:
    return f"{_slugify(brand)}-{_slugify(series)}-{_slugify(model)}"


# 2026-08-22: Fiorino/Doblo gibi seri altinda birden fazla kasa tipi
# (Combi/Cargo/Panorama) olan araclarda, taramadan gelen kayitlarda kasa
# tipi bazen "seri" alaninda (orn. seri="Fiorino Combi", model="1.3
# Multijet Premio"), bazen "model" alaninin basinda (orn. seri="Fiorino",
# model="Combi 1.3 Multijet Safeline") gorulebiliyor -- kaynak/sürüme
# gore degisiyor. Ayrica model genelde paket_fiyatlari.db'de OLMAYAN bir
# trim/donanim adi da icerir (Safeline, Pop, Premio, Easy, Maxi Plus...).
# paket_fiyatlari.db anahtari HER ZAMAN marka+SADECE-seri_adi (kasasiz,
# orn. "fiorino") + motor_adi (kasa+hacim, orn. "Fiorino Combi") +
# paket_adi (SADECE hacim/motor, orn. "1.3 Multijet") biciminde -- trim
# icermez. Bu yuzden tam slug eslesmesi (yukaridaki lookup_paket ana
# yolu) hem kasa alan farkliliginda hem trim kelimesi oldugunda basarisiz
# oluyordu -- found=False, Tahmini_Deger bos kaliyordu (Fiorino/Doblo
# varyantlarinda sistematik olarak).
#
# Cozum: "seri + model" (girilen tum serbest metni tek kelime dizisi
# olarak birlestirip) paket_db'deki HER olasi (seri_adi+motor_adi+
# paket_adi) kelime dizisiyle "en uzun onek eslesmesi" (longest prefix
# match) yontemiyle karsilastir -- kasa tipi ister seri'de ister model'de
# gelsin, ya da hic gelmesin (o zaman en genel/kisa eslesme secilir),
# sondaki fazladan trim kelimeleri sonucu etkilemez.
def _build_prefix_index(paket_db: dict) -> dict:
    """{'{category or "*"}:{marka_slug}': [(word_list, entry), ...]}

    word_list = seri_adi+motor_adi+paket_adi'nin BIRLESTIRILIP slugify
    edilmis "-" ile ayrilmis kelime listesi (orn. seri_adi="Fiorino",
    motor_adi="Fiorino Combi", paket_adi="1.3 Multijet" ->
    ['fiorino','combi','1','3','multijet'] -- motor_adi zaten seri_adi
    ile basladigi icin birlestirmede tekrar cikarilir).
    """
    index: dict = {}
    for entry in paket_db.values():
        marka_slug = entry.get("marka_slug") or ""
        seri_adi = entry.get("seri_adi") or ""
        motor_adi = entry.get("motor_adi") or ""
        paket_adi = entry.get("paket_adi") or ""
        if not marka_slug or not seri_adi:
            continue

        seri_words = [w for w in _slugify(seri_adi).split("-") if w]
        motor_words = [w for w in _slugify(motor_adi).split("-") if w]
        # motor_adi genelde seri_adi ile baslar (orn. seri="Fiorino",
        # motor="Fiorino Combi") -- tekrari at.
        if seri_words and motor_words[: len(seri_words)] == seri_words:
            motor_words = motor_words[len(seri_words):]
        paket_words = [w for w in _slugify(paket_adi).split("-") if w]

        words = seri_words + motor_words + paket_words
        if not words:
            continue

        cat = entry.get("_category") or "*"
        index.setdefault(f"{cat}:{marka_slug}", []).append((words, entry))
        index.setdefault(f"*:{marka_slug}", []).append((words, entry))
    return index


_prefix_index_cache: dict | None = None
_prefix_index_cache_id: int | None = None


def _get_prefix_index(paket_db: dict) -> dict:
    global _prefix_index_cache, _prefix_index_cache_id
    if _prefix_index_cache is None or _prefix_index_cache_id != id(paket_db):
        _prefix_index_cache = _build_prefix_index(paket_db)
        _prefix_index_cache_id = id(paket_db)
    return _prefix_index_cache


def _fuzzy_lookup_paket(
    paket_db: dict, brand: str, series: str, model: str, category: str | None,
) -> dict | None:
    marka_slug = _slugify(brand)
    if not marka_slug or (not series and not model):
        return None
    query = " ".join(p for p in (series, model) if p)
    query_words = [w for w in _slugify(query).split("-") if w]
    if not query_words:
        return None

    index = _get_prefix_index(paket_db)
    candidates = index.get(f"{category}:{marka_slug}") if category else None
    if not candidates:
        candidates = index.get(f"*:{marka_slug}")
    if not candidates:
        return None

    best_entry = None
    best_len = 0
    for words, entry in candidates:
        if len(words) > len(query_words):
            continue
        if words == query_words[: len(words)] and len(words) > best_len:
            best_len = len(words)
            best_entry = entry
    return best_entry


def lookup_paket(
    paket_db: dict,
    brand: str,
    series: str,
    model: str,
    year: int,
    category: str | None = None,
    min_samples: int | None = None,
) -> dict | None:
    """
    En spesifik seviye: paket (ya da paketi olmayan tek-donanimli motor).

    Yil bazli bucket yoktur - tek anlik referans nokta. Guvenilirlik
    korumasi sadece orneklem sayisina bakar (MIN_PAKET_SAMPLES); yil farki
    artik sinirlanmiyor, estimate_from_paket() bunu amortisman orani ile
    ekstrapole eder.

    Once tam slug eslesmesi denenir; basarisiz olursa (orn. model
    string'inde paket_db'de olmayan bir trim/donanim kelimesi varsa)
    ayni marka+seri altinda en uzun onek eslesen paket'e (_fuzzy_lookup_
    paket) dusulur -- bkz. yukaridaki not.
    """
    if not model or not paket_db:
        return None

    key = _paket_key(brand, series, model)
    entry = paket_db.get(f"{category}:{key}") if category else None
    if entry is None:
        entry = paket_db.get(key)
    if entry is None:
        entry = _fuzzy_lookup_paket(paket_db, brand, series, model, category)
        matched_key = None
    else:
        matched_key = key
    if entry is None:
        return None

    n = entry.get("fiyat_ornek_sayisi", 0)
    if n < (MIN_PAKET_SAMPLES if min_samples is None else min_samples):
        return None

    result = dict(entry)
    result["matched_key"] = matched_key or entry.get("paket_slug") or key
    return result


def _age_adjustment_factor(yil_farki: float) -> float:
    """Referans arac ile hedef arac arasindaki yas farkina (yil_farki =
    ref_year - year, pozitif: referans arac daha yeni/hedef daha eski)
    kademeli amortisman oranlarini (AGE_DEPRECIATION_BRACKETS) uygulayarak
    tek bir carpan dondurur.

    Sabit tek oranli eski davranistan farkli olarak, farkin her bir yil
    dilimi KENDI bracket'inin oranindan gecer -- orn. 10 yillik fark: ilk
    3 yil %4/yil, sonraki 5 yil (4-8 arasi) %2.5/yil, son 2 yil (8+) %1/yil
    olarak ayri ayri bilesik uygulanir (tum yil 10 icin en yuksek orandan
    hesaplanmaz). Fark negatifse (hedef arac referanstan daha YENI), ayni
    kademeler ters yonde (deger kazanci) uygulanir -- simetrik davranis.
    """
    if yil_farki == 0:
        return 1.0

    sign = 1.0 if yil_farki > 0 else -1.0
    remaining = abs(yil_farki)
    factor = 1.0
    prev_bound = 0.0

    for upper_bound, rate in AGE_DEPRECIATION_BRACKETS:
        if remaining <= 0:
            break
        bracket_span = (upper_bound - prev_bound) if upper_bound is not None else remaining
        years_in_bracket = min(remaining, bracket_span)
        factor *= (1 - rate) ** (sign * years_in_bracket)
        remaining -= years_in_bracket
        prev_bound = upper_bound if upper_bound is not None else prev_bound

    return factor


def _select_gear_variant(entry: dict, gear: str | None) -> tuple[dict, bool]:
    """entry['vites_bazli'] (bkz. hesapla_paket_fiyatlari.py 2026-08-11
    guncellemesi) varsa ve girilen aracin vitesine uygun bir alt-kayit
    mevcutsa, o alt-kaydi (kendi ortalama_fiyat/km/yil degerleriyle) dondurur
    -- bu durumda GERCEK vites-bazli veri kullanildigi icin sabit
    GEAR_MANUAL_PENALTY cezasi UYGULANMAZ (ikinci deger: used_real_gear_data
    True). Uygun alt-kayit yoksa (eski format ya da o vites icin veri
    toplanamamis), entry'nin kendisini (ust seviye best-variant ozeti)
    dondurur -- eski fallback davranisi (used_real_gear_data False, sabit
    ceza estimate_from_paket() icinde uygulanmaya devam eder).
    """
    variants = entry.get("vites_bazli")
    if not isinstance(variants, dict):
        return entry, False

    gear_key = "manuel" if _is_manual_gear(gear) else "otomatik"
    variant = variants.get(gear_key)
    # 2026-08-14: GPT/Codex incelemesi -- lookup_paket() MIN_PAKET_SAMPLES
    # kontrolunu SADECE ust seviye "en iyi varyant" ozetinde yapiyordu.
    # Ama burada secilen GERCEK vites-bazli varyant (orn. manuel) 1-2
    # ornekli olsa bile, ust seviye ozet (orn. otomatik, 50 ornekli) esigi
    # gectigi icin bu zayif varyant hic sorgulanmadan kullaniliyordu.
    # Artik secilen varyantin kendi orneklem sayisina da MIN_PAKET_SAMPLES
    # uygulaniyor -- yetersizse guvenilir ust seviye ozete (used_real_gear_data
    # False, sabit vites cezasiyla) geri donuluyor.
    if (
        isinstance(variant, dict)
        and variant.get("ortalama_fiyat") is not None
        and variant.get("fiyat_ornek_sayisi", 0) >= MIN_PAKET_SAMPLES
    ):
        return variant, True

    return entry, False


def estimate_from_paket(
    entry: dict,
    year: int,
    listing_km: float,
    damage: list[dict],
    gear: str | None = None,
) -> dict:
    """paket_fiyatlari kaydindan tahmini fiyat hesaplar (km_factor + damage_factor
    ayni sekilde uygulanir, ustune yil farki icin kademeli amortisman
    ekstrapolasyonu eklenir -- bkz. _age_adjustment_factor).

    gear: "Manuel" / "Otomatik" / "Yari Otomatik" (opsiyonel).

    2026-08-11: entry['vites_bazli'] alaninda girilen vitese uygun GERCEK
    referans veri varsa (bkz. _select_gear_variant), o veri dogrudan taban
    olarak kullanilir ve sabit GEAR_MANUAL_PENALTY cezasi UYGULANMAZ --
    cunku referans zaten o vitesteki gercek ilanlardan hesaplanmis, ustune
    ayrica ceza eklemek cifte sayim olurdu. Gercek veri yoksa (eski
    formatli kayit ya da o vites icin scraper hic ilan bulamamis), eski
    davranisa (otomatik varsayimli taban + manuel icin sabit %10 ceza)
    geri donulur.
    """
    base_entry, used_real_gear_data = _select_gear_variant(entry, gear)

    # 2026-09-18: gercek vites-bazli veri kimi paketlerde (az orneklem,
    # gurultu -- ozellikle eski/klasik modellerde) manuel varyanti otomatik
    # varyantindan DAHA YUKSEK fiyatli gosterebiliyor. Kullanicinin dogru
    # beklentisi hep gecerli: manuel vites otomatige gore FIYATI ASLA
    # YUKARI CEKMEMELI. Gercek veri kullanilirken manuel taban, ayni
    # paketin otomatik tabanindan yuksekse, cifte-ceza olmadan otomatik
    # tabana + sabit GEAR_MANUAL_PENALTY'e geri donulur.
    if used_real_gear_data and _is_manual_gear(gear):
        otomatik = (entry.get("vites_bazli") or {}).get("otomatik")
        if (
            isinstance(otomatik, dict)
            and otomatik.get("ortalama_fiyat") is not None
            and float(base_entry["ortalama_fiyat"]) > float(otomatik["ortalama_fiyat"])
        ):
            base_entry = otomatik
            used_real_gear_data = False

    base_price = float(base_entry["ortalama_fiyat"])
    base_km    = float(base_entry.get("ortalama_km") or 60_000)
    ref_year   = base_entry.get("ortalama_yil")

    if ref_year is not None:
        yil_farki = ref_year - year   # pozitif: referans arac daha yeni
        age_adj_factor = _age_adjustment_factor(yil_farki)
    else:
        age_adj_factor = 1.0

    adjusted_base = base_price * age_adj_factor

    kf = km_factor(listing_km, base_km)
    df = damage_factor(damage, adjusted_base)
    gf = 1.0 if used_real_gear_data else ((1.0 - GEAR_MANUAL_PENALTY) if _is_manual_gear(gear) else 1.0)

    estimated = adjusted_base * kf * df * gf

    # 2026-08-11: Onceden estimated, adjusted_base'in %30'unun altina asla
    # dusurulmuyordu (max(...,adjusted_base*0.30)) -- bu, gercekten agir
    # hasarli / asiri yuksek km'li araclarin tahminini yapay olarak
    # yukari cekip yanlis "en az bu kadar eder" sinyali veriyordu. Artik
    # taban kaldirildi; bunun yerine referans gruptan asiri sapma bir
    # bayrakla (extreme_low_confidence) isaretleniyor, cagiran taraf
    # (frontend/central_price_estimator) bunu "guven dusuk" seklinde
    # gosterebilir.
    combined_factor = kf * df * gf
    extreme_low_confidence = combined_factor < 0.30

    # 2026-08-24: Eski TEK global sabit (once 1.10, sonra ayrica central_
    # price_estimator'da 0.95 -- ikisi zincirleme, birbirinden habersiz)
    # yerine OLCULMUS marka/kategori bazli kalibrasyon carpani -- bkz.
    # yukaridaki CALIBRATION_FACTORS bloku ve _calibration_factor().
    # matched_key artik burada kullanilmiyor, entry/base_entry'nin kendi
    # marka_slug/_category alanlari kaynak.
    calib_factor = _calibration_factor(entry.get("marka_slug"), entry.get("_category"))
    estimated *= calib_factor

    return {
        "found":         True,
        "level":         "paket",
        "base_price":    round(adjusted_base, 2),
        "base_km":       round(base_km, 2),
        "base_count":    int(base_entry.get("fiyat_ornek_sayisi", 0)),
        "km_factor":     kf,
        "damage_factor": df,
        "gear_factor":   gf,
        "used_real_gear_data": used_real_gear_data,
        "calibration_factor": calib_factor,
        "tahmini_fiyat": int(round(estimated, -3)),
        "year_fallback": None,
        "matched_key":   entry.get("matched_key"),
        "extreme_low_confidence": extreme_low_confidence,
    }


# --- Factor calculators ------------------------------------------------------

# search_soldvehiclerecord uzerindeki 59.006 gercek satis kaydindan
# kurulan hedonic regresyondan (log(fiyat) ~ arac_varyanti + yas_spline +
# km_spline) cikarilan, km=0 referansina gore normalize edilmis carpan
# egrisi. 5.000 km araliklarla ornekklenmis, monoton azalan (PAVA ile
# duzeltilmis -- 0-10k araliginda regresyonun uc noktalarda gosterdigi
# kucuk "artis" gurultusu/secilim etkisi olabilir, gercek km-fiyat iliskisi
# monoton azalan olmalidir). km_factor() bu tabloyu dogrusal interpolasyonla
# okur. Tablo disina (300k+ km) sabit ekstrapole edilir.
#
# Ornek okuma: 0 km -> 1.0, 100.000 km -> ~0.808 (referansa gore %19.2 dusuk),
# 115.000 km -> ~0.795 (%20.5 dusuk).
KM_CURVE_POINTS = [
    (0, 1.0000), (5000, 0.9877), (10000, 0.9755), (15000, 0.9534),
    (20000, 0.9318), (25000, 0.9232), (30000, 0.9148), (35000, 0.9068),
    (40000, 0.8989), (45000, 0.8910), (50000, 0.8832), (55000, 0.8761),
    (60000, 0.8691), (65000, 0.8621), (70000, 0.8552), (75000, 0.8471),
    (80000, 0.8390), (85000, 0.8311), (90000, 0.8232), (95000, 0.8154),
    (100000, 0.8077), (105000, 0.8034), (110000, 0.7992), (115000, 0.7949),
    (120000, 0.7907), (125000, 0.7866), (130000, 0.7824), (135000, 0.7783),
    (140000, 0.7741), (145000, 0.7700), (150000, 0.7660), (155000, 0.7590),
    (160000, 0.7520), (165000, 0.7452), (170000, 0.7384), (175000, 0.7316),
    (180000, 0.7249), (185000, 0.7183), (190000, 0.7117), (195000, 0.7052),
    (200000, 0.6988), (205000, 0.6926), (210000, 0.6865), (215000, 0.6804),
    (220000, 0.6743), (225000, 0.6684), (230000, 0.6624), (235000, 0.6566),
    (240000, 0.6507), (245000, 0.6450), (250000, 0.6392), (255000, 0.6336),
    (260000, 0.6280), (265000, 0.6224), (270000, 0.6169), (275000, 0.6114),
    (280000, 0.6060), (285000, 0.6006), (290000, 0.5953), (295000, 0.5900),
    (300000, 0.5848),
]
_KM_CURVE_XP = [p[0] for p in KM_CURVE_POINTS]
_KM_CURVE_FP = [p[1] for p in KM_CURVE_POINTS]


def _km_curve_value(km: float) -> float:
    """KM_CURVE_POINTS tablosunu dogrusal interpolasyonla okur (referans
    km=0'a gore normalize edilmis carpan). Tablo araligi disinda (km<0 ya da
    km>300.000) en yakin uc noktaya sabit ekstrapole edilir (kesin veri
    olmayan bolgede egriyi agresif sekilde disari uzatmamak icin)."""
    km = max(0.0, km)
    if km <= _KM_CURVE_XP[0]:
        return _KM_CURVE_FP[0]
    if km >= _KM_CURVE_XP[-1]:
        return _KM_CURVE_FP[-1]
    # ikili arama yerine tablo kucuk oldugu icin (61 nokta) dogrusal tarama yeterli
    for i in range(1, len(_KM_CURVE_XP)):
        if km <= _KM_CURVE_XP[i]:
            x0, x1 = _KM_CURVE_XP[i - 1], _KM_CURVE_XP[i]
            y0, y1 = _KM_CURVE_FP[i - 1], _KM_CURVE_FP[i]
            t = (km - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return _KM_CURVE_FP[-1]


def km_factor(listing_km: float, base_km: float) -> float:
    """KM farkinin fiyata etkisini hesaplar.

    2026-08-22: Eski sabit-adim + sondurme formulu (KM_STEP_PCT +
    KM_STEP_DAMPING) yerine, search_soldvehiclerecord uzerindeki 59.006
    gercek satis kaydindan cikarilan KM_CURVE_POINTS referans egrisi
    kullanilir (bkz. yukaridaki degisken tanimlari ve yorumlari). Egri
    yastan (arac yasi ayni regresyonda ayri bir terim olarak kontrol
    edilerek) ayristirilmis "saf" km etkisini temsil eder.

    Hesap: hem ilan_km hem referans (base) km icin egriden bir "0 km'ye
    gore carpan" degeri okunur, orani alinir -- boylece sonuc, base_km'nin
    KENDISI referans noktasi olacak sekilde normalize edilir (eskiden de
    boyleydi: factor(base_km, base_km) == 1.0 olmasi gerekir)."""
    if base_km <= 0 or listing_km < 0:
        return 1.0
    base_curve = _km_curve_value(base_km)
    listing_curve = _km_curve_value(listing_km)
    if base_curve <= 0:
        return 1.0
    factor = listing_curve / base_curve
    return max(KM_FACTOR_MIN, min(KM_FACTOR_MAX, factor))


def damage_factor(damage_list: list[dict], base_price: float) -> float:
    """
    Returns a multiplier (0-1) to apply to base_price.

    Kritik parcalar (tavan, motor kaputu) her zaman tam agirlikla sayilir.
    Kritik olmayan parcalar (kapilar dahil) icin art arda eklenen her yeni
    boyali/lokal boyali/degisen parca, bir onceki en etkili parcaya gore
    NON_CRITICAL_STACK_DECAY orani kadar azalan agirlikla sayilir -- yani
    "2. kapi boyaliyken fiyat 1. kapi kadar dusmez" mantigi.

    Agir hasarli -> additional flat -15% (butun bunlarin ustune, ayrik).
    """
    if not damage_list or base_price <= 0:
        return 1.0

    has_agir = False
    critical_pct = 0.0
    noncritical_pcts: list[float] = []

    for item in damage_list:
        parca = str(item.get("parca", "")).lower().strip()
        durum = str(item.get("durum", "")).lower().strip()

        if durum in ("orijinal", ""):
            continue
        if "ağır" in durum or "agir" in durum:
            has_agir = True
            continue

        penalty = DURUM_PENALTY.get(durum, 0.0)
        if not penalty:
            continue

        if parca in CRITICAL:
            critical_pct += penalty * 5.0
        else:
            tier = 2.0 if parca in MAJOR else 1.0
            noncritical_pcts.append(penalty * tier)

    # En etkili kritik-olmayan parca tam agirlikla, sonrakiler azalarak sayilir.
    noncritical_pcts.sort(reverse=True)
    noncritical_total = sum(
        pct * (NON_CRITICAL_STACK_DECAY ** i) for i, pct in enumerate(noncritical_pcts)
    )

    total_pct = critical_pct + noncritical_total
    factor = max(0.0, 1.0 - total_pct)
    if has_agir:
        factor *= (1.0 - AGIR_HASAR_FLAT)

    return round(factor, 4)


# --- Main estimator -----------------------------------------------------------

def estimate_price(
    brand: str,
    series: str,
    model: str,      # raw model/paket string e.g. "1.6 Multijet Easy"
    year: int,
    listing_km: float,
    damage: list[dict] | None = None,
    paket_db: dict | None = None,
    gear: str | None = None,
    min_samples: int | None = None,
) -> dict:
    """
    Returns:
        {
          "found":          bool,
          "level":          "paket" | None,
          "base_price":     float | None,
          "base_km":        float | None,
          "base_count":     int,
          "km_factor":      float,
          "damage_factor":  float,
          "gear_factor":    float,
          "tahmini_fiyat":  int | None,
          "year_fallback":  int | None,
          "matched_key":    str | None,
        }

    Tek fiyat kaynagi paket_fiyatlari.json / paket_fiyatlari_suv.json
    (bkz. load_paket_baseline()). Guvenilirlik korumalari (orneklem /
    yil farki) gecmezse veya eslesme yoksa found=False doner.

    gear: bkz. estimate_from_paket() -- sadece manuel vites icin
    GEAR_MANUAL_PENALTY kadar ek indirim uygular.
    """
    damage = damage or []

    if paket_db:
        paket_entry = lookup_paket(paket_db, brand, series, model, year, min_samples=min_samples)
        if paket_entry is not None:
            return estimate_from_paket(paket_entry, year, listing_km, damage, gear=gear)

    return {
        "found": False, "level": None,
        "base_price": None, "base_km": None, "base_count": 0,
        "km_factor": 1.0, "damage_factor": 1.0, "gear_factor": 1.0,
        "used_real_gear_data": False,
        "tahmini_fiyat": None, "year_fallback": None, "matched_key": None,
        "extreme_low_confidence": False,
    }


# --- CLI quick-test ------------------------------------------------------------

if __name__ == "__main__":
    import sys
    paket_db = load_paket_baseline()
    if not paket_db:
        print("paket_fiyatlari.json / paket_fiyatlari_suv.json bulunamadi.")
        sys.exit(1)

    print(f"Paket DB: {len(paket_db)} toplam kayit\n")

    result = estimate_price(
        brand="fiat", series="egea",
        model="1.6 Multijet Easy",
        year=2020, listing_km=90_000,
        damage=[
            {"parca": "Sol Ön Kapı", "durum": "Boyalı"},
            {"parca": "Sağ Ön Kapı", "durum": "Boyalı"},
            {"parca": "Çamurluk",    "durum": "Değişmiş"},
        ],
        paket_db=paket_db,
        gear="Manuel",
    )
    print("Ornek tahmin (Fiat Egea 1.6 Multijet Easy 2020, Manuel):")
    for k, v in result.items():
        print(f"  {k}: {v}")
