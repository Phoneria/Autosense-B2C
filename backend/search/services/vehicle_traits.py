"""
vehicle_traits.py — Araç kronik / iyi / kötü özelliklerinin okunması.

Veri kaynağı `data/vehicle_traits.db`; `scripts/build_traits_db.py` üretir.
Bu modül SADECE okur — LLM yok, çıkarım yok, hesap yok. Aynı araç için her
zaman aynı çıktıyı döner.

Veritabanı değişince (yeni araç verisi üretilip betik çalıştırılınca) bağlantı
dosyanın mtime'ına bakarak kendini tazeler; servisi yeniden başlatmak gerekmez.
"""
from __future__ import annotations

import re
import sqlite3
import threading
import unicodedata
from pathlib import Path

from django.conf import settings

from ..pricing.reference import readonly_connection

TIPLER = ("kronik", "iyi", "kotu")

_yerel = threading.local()


def normalize(s: str) -> str:
    """Eşleştirme anahtarı. scripts/build_traits_db.py::normalize ile
    BİREBİR aynı olmak zorunda — biri değişirse eşleşme sessizce bozulur."""
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("İ", "i").replace("I", "ı").lower()
    s = s.translate(str.maketrans("ığüşöç", "igusoc"))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def arac_anahtari(brand: str, series: str, engine: str) -> str:
    return normalize(f"{brand} {series} {engine}")


def _conn() -> sqlite3.Connection | None:
    """Dosya yoksa None döner — veri üretilmemişse özellik sessizce kapalı kalır."""
    yol = Path(str(settings.B2C_TRAITS_DB))
    try:
        mtime = yol.stat().st_mtime_ns
    except OSError:
        return None

    conn = getattr(_yerel, "conn", None)
    if conn is not None and (getattr(_yerel, "yol", None) != str(yol)
                             or getattr(_yerel, "mtime", None) != mtime):
        conn.close()
        conn = None
    if conn is None:
        try:
            conn = readonly_connection(yol)
        except (sqlite3.Error, OSError, FileNotFoundError):
            return None
        _yerel.conn = conn
        _yerel.yol = str(yol)
        _yerel.mtime = mtime
    return conn


def _kayitlar(conn: sqlite3.Connection, anahtar: str) -> dict[str, list[dict]]:
    satirlar = conn.execute(
        "SELECT tip, etiket, iddia, km_araligi, kaynak_url, kaynak_alan, "
        "kaynak_alinti, guven FROM traits WHERE arac_anahtar = ? ORDER BY tip, sira",
        (anahtar,)).fetchall()
    gruplar: dict[str, list[dict]] = {t: [] for t in TIPLER}
    for r in satirlar:
        if r["tip"] in gruplar:
            gruplar[r["tip"]].append({
                "etiket": r["etiket"], "iddia": r["iddia"],
                "km_araligi": r["km_araligi"],
                "kaynak_url": r["kaynak_url"], "kaynak_alan": r["kaynak_alan"],
                "kaynak_alinti": r["kaynak_alinti"], "guven": r["guven"],
            })
    return gruplar


def arac_listesi() -> list[dict]:
    """Seçim kutusu için veri bulunan araçların listesi (ilan sayısına göre)."""
    conn = _conn()
    if conn is None:
        return []
    return [{
        "anahtar": r["anahtar"], "etiket": r["etiket"],
        "marka": r["marka"], "seri": r["seri"], "motor": r["motor"],
        "yil_baslangic": r["yil_baslangic"], "yil_bitis": r["yil_bitis"],
        "kronik_n": r["kronik_n"], "iyi_n": r["iyi_n"], "kotu_n": r["kotu_n"],
    } for r in conn.execute(
        "SELECT anahtar, etiket, marka, seri, motor, yil_baslangic, yil_bitis, "
        "kronik_n, iyi_n, kotu_n FROM vehicles "
        "ORDER BY ilan_sayisi IS NULL, ilan_sayisi DESC, etiket")]


def _bos(anahtar: str, etiket: str) -> dict:
    return {"available": False, "anahtar": anahtar, "etiket": etiket,
            "kronik": [], "iyi": [], "kotu": [], "kaynak_n": 0,
            "yil_baslangic": None, "yil_bitis": None}


def arac_ozellikleri(anahtar: str, *, gosterim_adi: str = "") -> dict:
    """Tek aracın özellikleri. Eşleşme SADECE tam marka+seri+motor üzerinden;
    yaklaşık eşleştirme yok — kronik arıza motora özgüdür, komşu motorun
    verisini göstermek yanlış bilgi olur."""
    anahtar = normalize(anahtar)
    conn = _conn()
    if conn is None or not anahtar:
        return _bos(anahtar, gosterim_adi)

    arac = conn.execute(
        "SELECT anahtar, etiket, yil_baslangic, yil_bitis, kaynak_n "
        "FROM vehicles WHERE anahtar = ?", (anahtar,)).fetchone()
    if arac is None:
        return _bos(anahtar, gosterim_adi)

    gruplar = _kayitlar(conn, anahtar)
    return {
        "available": any(gruplar[t] for t in TIPLER),
        "anahtar": arac["anahtar"], "etiket": arac["etiket"],
        "yil_baslangic": arac["yil_baslangic"], "yil_bitis": arac["yil_bitis"],
        "kaynak_n": arac["kaynak_n"],
        **gruplar,
    }


def analiz_icin(brand: str, series: str, engine: str) -> dict:
    """analyze() çıktısına gömülen blok."""
    gosterim = " ".join(x for x in (brand, series, engine) if x).strip()
    return arac_ozellikleri(arac_anahtari(brand, series, engine), gosterim_adi=gosterim)
