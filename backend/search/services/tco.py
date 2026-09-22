"""
tco.py
======
"Toplam Sahip Olma Maliyeti" (Total Cost of Ownership) — kaba/yaklaşık
yıllık maliyet tahmini: MTV + yakıt + sigorta (kasko + trafik) + bakım.

Bu bir muhasebe/teklif aracı DEĞİLDİR. Tüm kalemler kaba varsayımlara
dayanır (bkz. sabitler aşağıda) ve gerçek sigorta teklifi / servis
faturası yerine geçmez. Amaç, bir ilanın "gerçek maliyetine" dair kabaca
bir fikir vermektir.

MTV hesaplaması Arabam Otomasyon/Inputs/MTVCalculator.py'deki resmi
tarifeyi kullanır (aynı proje içinde zaten var olan, ayrı bir yerde
elle tekrar yazmak yerine buradan import edilir).
"""

from __future__ import annotations

import re
import sys
from datetime import datetime

from ..pricing.mtv import hesapla_mtv


YILLIK_KM_VARSAYIM = 20_000  # sabit varsayım (kullanıcıdan girdi alınmıyor)

# --- Kaba sabitler (Temmuz 2026 ortalamaları) -------------------------------
# Akaryakıt/elektrik fiyatları sık değiştiği için bunlar periyodik olarak
# elle güncellenmeli. Amaç kesin fiyat değil, büyüklük mertebesi vermek.
YAKIT_FIYATI_TL = {
    "benzin": 67.0,    # TL / litre
    "dizel": 75.0,     # TL / litre
    "lpg": 31.0,       # TL / litre
    "elektrik": 4.5,   # TL / kWh (kademeli mesken tarifesi ortalaması)
}
ORTALAMA_TUKETIM = {
    "benzin": 7.0,      # L / 100km
    "dizel": 5.5,       # L / 100km
    "lpg": 9.0,         # L / 100km
    "elektrik": 18.0,   # kWh / 100km
}

KASKO_ORANI = 0.035          # taşıt değerinin yüzdesi / yıl (kaba)
TRAFIK_SIGORTASI_TL = 6500   # yıllık, kaba ortalama (2026 tavan fiyatların altı)
BAKIM_ORANI = 0.015          # taşıt değerinin yüzdesi / yıl (kaba)
BAKIM_TABAN_TL = 10_000      # düşük değerli araçlarda dahi altına inmeyecek taban


def _guess_fuel_and_cc(engine_str: str) -> tuple[str, int | None]:
    """Fiyat Tahmini formundaki serbest metin 'engine' alanından (örn.
    '2.0 TDI', '1.6 TSI', 'Elektrikli') yakıt tipini ve motor hacmini (cc)
    kaba şekilde çıkarır. Kesin değil — tahmin."""
    s = (engine_str or "").lower()

    if any(k in s for k in ["elektrik", "electric", "ev", "e-tron", "e-golf", "e-208"]):
        return "elektrik", None

    if "lpg" in s:
        fuel = "lpg"
    elif any(k in s for k in [
        "tdi", "dci", "hdi", "crdi", "cdti", "d4d", "dizel", "diesel",
        "multijet", "bluehdi", "cdi", "tdci",
    ]):
        fuel = "dizel"
    else:
        fuel = "benzin"

    cc = None
    m = re.search(r"(\d[.,]\d)", engine_str or "")
    if m:
        try:
            liters = float(m.group(1).replace(",", "."))
            if 0.5 <= liters <= 8.0:
                cc = int(round(liters * 1000))
        except ValueError:
            cc = None

    return fuel, cc


def compute_tco(
    *,
    engine: str,
    year: int,
    estimated_value: int | float | None,
    annual_km: int = YILLIK_KM_VARSAYIM,
) -> dict:
    """Kaba yıllık toplam sahip olma maliyeti. `estimated_value` yoksa
    (None/0) sigorta ve bakım kalemleri de 0 olarak dönmez — taban
    değerler üzerinden hesaplanır, sadece kasko/bakım'ın değere bağlı
    kısmı 0 olur."""
    fuel, cc = _guess_fuel_and_cc(engine)
    arac_yasi = max(datetime.now().year - int(year), 0) or 1
    tasit_degeri = int(estimated_value) if estimated_value else 0

    # --- MTV ---
    mtv_amount = None
    mtv_note = None
    if fuel == "elektrik":
        mtv_note = "Elektrikli araçlar için motor gücü (kW) bilinmediğinden MTV hesaplanamadı."
    elif fuel == "lpg":
        mtv_note = "LPG'li araçlar için ayrı MTV tarifesi bulunmuyor, hesaplama atlandı."
    elif cc is None:
        mtv_note = "Motor hacmi ilan bilgisinden çözümlenemedi, MTV hesaplanamadı."
    else:
        mtv_result = hesapla_mtv(
            motor_hacmi_cc=cc, tasit_degeri_tl=tasit_degeri,
            arac_yasi=arac_yasi, yakit_tipi=fuel,
        )
        if "error" not in mtv_result:
            mtv_amount = mtv_result["mtv_tutari"]
        else:
            mtv_note = mtv_result["error"]

    # --- Yakıt ---
    tuketim = ORTALAMA_TUKETIM.get(fuel, ORTALAMA_TUKETIM["benzin"])
    birim_fiyat = YAKIT_FIYATI_TL.get(fuel, YAKIT_FIYATI_TL["benzin"])
    yakit_yillik = (annual_km / 100.0) * tuketim * birim_fiyat

    # --- Sigorta (kasko + trafik) ---
    kasko_yillik = tasit_degeri * KASKO_ORANI
    sigorta_yillik = kasko_yillik + TRAFIK_SIGORTASI_TL

    # --- Bakım ---
    bakim_yillik = max(tasit_degeri * BAKIM_ORANI, BAKIM_TABAN_TL)

    toplam = (mtv_amount or 0) + yakit_yillik + sigorta_yillik + bakim_yillik

    return {
        "yakit_tipi_tahmini": fuel,
        "motor_hacmi_cc_tahmini": cc,
        "arac_yasi": arac_yasi,
        "yillik_km_varsayimi": annual_km,
        "mtv": {
            "yillik_tl": mtv_amount,
            "not": mtv_note,
        },
        "yakit": {
            "yillik_tl": round(yakit_yillik),
            "ortalama_tuketim": tuketim,
            "birim_fiyat_tl": birim_fiyat,
            "birim": "kWh" if fuel == "elektrik" else "L",
        },
        "sigorta": {
            "yillik_tl": round(sigorta_yillik),
            "kasko_tahmini_tl": round(kasko_yillik),
            "trafik_sigortasi_tahmini_tl": TRAFIK_SIGORTASI_TL,
        },
        "bakim": {
            "yillik_tl": round(bakim_yillik),
        },
        "toplam_yillik_tl": round(toplam),
        "toplam_aylik_tl": round(toplam / 12),
        "uyari": (
            "Tüm kalemler kaba tahminlerdir (Temmuz 2026 ortalama akaryakıt/"
            "elektrik fiyatları ile tipik kasko/bakım oranları baz alınmıştır); "
            "gerçek sigorta teklifi veya servis faturası yerine geçmez."
        ),
    }


def compute_personal_tco(
    *, engine: str, year: int, annual_km: int, vehicle_value: float | None = None,
    fuel: str | None = None, consumption: float | None = None, unit_price: float | None = None,
    kasko_tl: float | None = None, traffic_tl: float | None = None, maintenance_tl: float | None = None,
    parking_monthly_tl: float = 0, tires_tl: float = 0, inspection_tl: float = 0,
    toll_monthly_tl: float = 0, other_tl: float = 0, loan_monthly_tl: float = 0,
) -> dict:
    """Kullanıcının kendi değerleriyle yıllık maliyet. Boş bırakılan her kalem
    genel varsayımla doldurulur ve `estimated=True` işaretlenir."""
    guessed_fuel, cc = _guess_fuel_and_cc(engine)
    fuel = fuel or guessed_fuel
    energy = "benzin" if fuel == "hibrit" else fuel
    value = int(vehicle_value) if vehicle_value else 0
    age = max(datetime.now().year - int(year), 0) or 1

    lines: list[dict] = []

    def add(key, label, yearly, estimated, note=None):
        lines.append({"key": key, "label": label, "yearly_tl": round(yearly or 0),
                      "monthly_tl": round((yearly or 0) / 12), "estimated": estimated, "note": note})

    default_consumption = 4.8 if fuel == "hibrit" else ORTALAMA_TUKETIM.get(energy, ORTALAMA_TUKETIM["benzin"])
    used_consumption = consumption if consumption is not None else default_consumption
    used_price = unit_price if unit_price is not None else YAKIT_FIYATI_TL.get(energy, YAKIT_FIYATI_TL["benzin"])
    unit = "kWh" if energy == "elektrik" else "L"
    add("fuel", "Yakıt / enerji", annual_km / 100 * used_consumption * used_price,
        consumption is None or unit_price is None,
        f"{annual_km:,} km × {used_consumption:g} {unit}/100 km × {used_price:g} TL".replace(",", "."))

    mtv_amount, mtv_note = None, None
    if energy == "elektrik":
        mtv_note = "Elektrikli araçlarda motor gücü bilinmediği için MTV hesaplanamadı."
    elif energy == "lpg":
        mtv_note = "LPG'li araçlar için MTV hesaplanmadı."
    elif cc is None:
        mtv_note = "Motor hacmi çözümlenemedi, MTV hesaplanamadı."
    else:
        r = hesapla_mtv(motor_hacmi_cc=cc, tasit_degeri_tl=value, arac_yasi=age, yakit_tipi=energy)
        if "error" in r:
            mtv_note = r["error"]
        else:
            mtv_amount = r["mtv_tutari"]
    add("mtv", "MTV", mtv_amount or 0, False, mtv_note or "Resmî tarifeye göre")

    add("kasko", "Kasko", kasko_tl if kasko_tl is not None else value * KASKO_ORANI, kasko_tl is None,
        None if kasko_tl is not None else "Araç değerinin ~%3,5'i (kendi teklifinizi girin)")
    add("traffic", "Trafik sigortası", traffic_tl if traffic_tl is not None else TRAFIK_SIGORTASI_TL,
        traffic_tl is None, None if traffic_tl is not None else "Ortalama değer")
    add("maintenance", "Bakım", maintenance_tl if maintenance_tl is not None else max(value * BAKIM_ORANI, BAKIM_TABAN_TL),
        maintenance_tl is None, None if maintenance_tl is not None else "Araç değerinin ~%1,5'i, en az 10.000 TL")
    if parking_monthly_tl:
        add("parking", "Otopark", parking_monthly_tl * 12, False)
    if toll_monthly_tl:
        add("toll", "Köprü / otoyol", toll_monthly_tl * 12, False)
    if tires_tl:
        add("tires", "Lastik", tires_tl, False)
    if inspection_tl:
        add("inspection", "Muayene / egzoz", inspection_tl, False)
    if other_tl:
        add("other", "Diğer", other_tl, False)
    if loan_monthly_tl:
        add("loan", "Kredi taksiti", loan_monthly_tl * 12, False)

    total = sum(line["yearly_tl"] for line in lines)
    running = sum(line["yearly_tl"] for line in lines if line["key"] != "loan")
    return {
        "fuel": fuel,
        "engine_cc": cc,
        "annual_km": annual_km,
        "lines": lines,
        "total_yearly_tl": total,
        "total_monthly_tl": round(total / 12),
        "per_km_tl": round(running / annual_km, 2) if annual_km else None,
        "estimated_count": sum(1 for line in lines if line["estimated"]),
    }
