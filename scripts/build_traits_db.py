#!/usr/bin/env python3
"""
build_traits_db.py — Araç kronik / iyi / kötü özellik veritabanını üretir.

Girdi : research/kronik-pilot/ciktilar_uretim/B/*.json  (doğrulanmış üretim çıktıları)
        research/kronik-pilot/targets_production.json   (araç üstverisi)
Çıktı : data/vehicle_traits.db                          (atomik değiştirilir)

Yeni araç verisi ürettikten sonra SADECE bu betiği çalıştır; uygulama kodunda
değişiklik gerekmez. Backend veritabanının mtime'ına bakar, yeniden başlatma da
gerekmez.

    python3 scripts/build_traits_db.py
    python3 scripts/build_traits_db.py --kuru      # yazma, sadece ne olacağını göster
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
GIRDI = ROOT / "research" / "kronik-pilot" / "ciktilar_uretim" / "B"
HEDEFLER = ROOT / "research" / "kronik-pilot" / "targets_production.json"
CIKTI = ROOT / "data" / "vehicle_traits.db"

# ───────────────────────────────────────────────────────────────────────────
# FİLTRE AYARLARI
# ───────────────────────────────────────────────────────────────────────────
# Pilot değerlendirmesi (research/kronik-pilot/degerlendirme.csv) bitene kadar
# eşik KOYULMUYOR. Eşik koymak, hangi seviyede hata oranının kabul edilebilir
# olduğunu bilmeden tahmin yürütmek olurdu.
#
# Değerlendirme bitince burayı düzenle ve betiği yeniden çalıştır; ne backend
# ne frontend değişir.
FILTRE = {
    # Kabul edilen güven seviyeleri. Örn. {"yuksek", "orta"} → düşükler elenir.
    "guven": None,                  # None = hepsi

    # Sadece bu alan adlarından gelen kayıtlar kabul edilsin. Örn:
    # {"forum.donanimhaber.com", "www.sikayetvar.com", "otopark.com"}
    "izinli_alan_adlari": None,     # None = hepsi

    # Bir araç için bir tipte en az kaç kayıt olmalı ki o tip gösterilsin.
    "tip_basina_min_kayit": 1,

    # Aynı etiketten en fazla kaç kayıt tutulsun (tekrar eden iddiaları kırpar).
    "etiket_basina_azami": 2,
}

TIPLER = ("kronik", "iyi", "kotu")

SEMA = """
CREATE TABLE vehicles (
    anahtar       TEXT PRIMARY KEY,   -- normalize "marka seri motor"
    marka         TEXT NOT NULL,
    seri          TEXT NOT NULL,
    motor         TEXT NOT NULL,
    etiket        TEXT NOT NULL,      -- gösterim adı: "Renault Clio 1.5 dCi"
    ilan_sayisi   INTEGER,
    medyan_yil    INTEGER,
    yas_grubu     TEXT,
    yil_baslangic INTEGER,
    yil_bitis     INTEGER,
    kronik_n      INTEGER NOT NULL DEFAULT 0,
    iyi_n         INTEGER NOT NULL DEFAULT 0,
    kotu_n        INTEGER NOT NULL DEFAULT 0,
    kaynak_n      INTEGER NOT NULL DEFAULT 0,
    uretim_modeli TEXT
);

CREATE TABLE traits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    arac_anahtar  TEXT NOT NULL REFERENCES vehicles(anahtar) ON DELETE CASCADE,
    tip           TEXT NOT NULL,      -- kronik | iyi | kotu
    etiket        TEXT NOT NULL,      -- kapalı etiket setinden
    iddia         TEXT NOT NULL,
    km_araligi    TEXT,
    kaynak_url    TEXT NOT NULL,
    kaynak_alan   TEXT NOT NULL,      -- URL'in alan adı
    kaynak_alinti TEXT,
    guven         TEXT NOT NULL,
    sira          INTEGER NOT NULL
);

CREATE INDEX traits_arac ON traits(arac_anahtar, tip, sira);

CREATE TABLE meta (anahtar TEXT PRIMARY KEY, deger TEXT NOT NULL);
"""

GUVEN_SIRASI = {"yuksek": 0, "orta": 1, "dusuk": 2}


def normalize(s: str) -> str:
    """Eşleştirme anahtarı. Backend aynı fonksiyonu kullanır —
    backend/search/services/vehicle_traits.py::normalize ile birebir aynı kalmalı."""
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("İ", "i").replace("I", "ı").lower()
    s = s.translate(str.maketrans("ığüşöç", "igusoc"))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def alan_adi(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except ValueError:
        return ""


def gecer_mi(kayit: dict) -> bool:
    if FILTRE["guven"] and kayit.get("guven") not in FILTRE["guven"]:
        return False
    izin = FILTRE["izinli_alan_adlari"]
    if izin and alan_adi(kayit.get("kaynak_url", "")) not in izin:
        return False
    return True


def hedef_ustverisi() -> dict[str, dict]:
    if not HEDEFLER.exists():
        return {}
    veri = json.loads(HEDEFLER.read_text(encoding="utf-8"))
    return {h["id"]: h for h in veri.get("hedefler", [])}


def dosyalari_oku(ustveri: dict[str, dict]) -> tuple[list[dict], list[dict], list[str]]:
    araclar, kayitlar, atlanan = [], [], []
    for yol in sorted(GIRDI.glob("*.json")):
        try:
            veri = json.loads(yol.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            atlanan.append(f"{yol.name}: bozuk JSON")
            continue

        hedef_id = veri.get("hedef_id") or yol.stem.split("__")[0]
        h = ustveri.get(hedef_id)
        if not h:
            atlanan.append(f"{yol.name}: {hedef_id} targets_production.json'da yok")
            continue

        anahtar = normalize(h["etiket"])
        secilen: list[dict] = []
        etiket_sayaci: dict[tuple, int] = {}

        # Güveni yüksek olan önce gelsin ki etiket kırpması iyi kayıtları korusun.
        for k in sorted(veri.get("kayitlar", []),
                        key=lambda x: GUVEN_SIRASI.get(x.get("guven"), 9)):
            if k.get("tip") not in TIPLER or not gecer_mi(k):
                continue
            ikili = (k["tip"], k["etiket"])
            if etiket_sayaci.get(ikili, 0) >= FILTRE["etiket_basina_azami"]:
                continue
            etiket_sayaci[ikili] = etiket_sayaci.get(ikili, 0) + 1
            secilen.append(k)

        sayim = {t: sum(1 for k in secilen if k["tip"] == t) for t in TIPLER}
        for t, n in sayim.items():
            if 0 < n < FILTRE["tip_basina_min_kayit"]:
                secilen = [k for k in secilen if k["tip"] != t]
                sayim[t] = 0
        if not secilen:
            atlanan.append(f"{yol.name}: filtre sonrası kayıt kalmadı")
            continue

        yil = h.get("yil_araligi") or [None, None]
        araclar.append({
            "anahtar": anahtar, "marka": h["marka"], "seri": h["seri"],
            "motor": h["motor"], "etiket": h["etiket"],
            "ilan_sayisi": h.get("ilan_sayisi"), "medyan_yil": h.get("medyan_yil"),
            "yas_grubu": h.get("yas_grubu"),
            "yil_baslangic": yil[0], "yil_bitis": yil[1],
            "kronik_n": sayim["kronik"], "iyi_n": sayim["iyi"], "kotu_n": sayim["kotu"],
            "kaynak_n": len({k.get("kaynak_url") for k in secilen}),
            "uretim_modeli": veri.get("model"),
        })
        for sira, k in enumerate(secilen):
            kayitlar.append({
                "arac_anahtar": anahtar, "tip": k["tip"], "etiket": k["etiket"],
                "iddia": k["iddia"], "km_araligi": k.get("km_araligi"),
                "kaynak_url": k.get("kaynak_url") or "",
                "kaynak_alan": alan_adi(k.get("kaynak_url", "")),
                "kaynak_alinti": k.get("kaynak_alinti"),
                "guven": k.get("guven") or "dusuk", "sira": sira,
            })
    return araclar, kayitlar, atlanan


def yaz(araclar: list[dict], kayitlar: list[dict]) -> None:
    """SQLite dosyasi YEREL diskte kurulur, sonra hedefe kopyalanip atomik
    degistirilir. Sebep: bagli klasorler (ag/FUSE mount) SQLite'in ihtiyac
    duydugu kilitlemeyi desteklemiyor, dogrudan yazim 'disk I/O error' veriyor."""
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(suffix=".db")      # sistem gecici dizini = yerel disk
    os.close(fd)
    try:
        with sqlite3.connect(gecici) as db:
            db.executescript(SEMA)
            db.executemany(
                "INSERT INTO vehicles (anahtar,marka,seri,motor,etiket,ilan_sayisi,"
                "medyan_yil,yas_grubu,yil_baslangic,yil_bitis,kronik_n,iyi_n,kotu_n,"
                "kaynak_n,uretim_modeli) VALUES (:anahtar,:marka,:seri,:motor,:etiket,"
                ":ilan_sayisi,:medyan_yil,:yas_grubu,:yil_baslangic,:yil_bitis,"
                ":kronik_n,:iyi_n,:kotu_n,:kaynak_n,:uretim_modeli)", araclar)
            db.executemany(
                "INSERT INTO traits (arac_anahtar,tip,etiket,iddia,km_araligi,"
                "kaynak_url,kaynak_alan,kaynak_alinti,guven,sira) VALUES "
                "(:arac_anahtar,:tip,:etiket,:iddia,:km_araligi,:kaynak_url,"
                ":kaynak_alan,:kaynak_alinti,:guven,:sira)", kayitlar)
            db.executemany("INSERT INTO meta VALUES (?,?)", [
                ("uretim_zamani", datetime.now(timezone.utc).isoformat(timespec="seconds")),
                ("arac_sayisi", str(len(araclar))),
                ("kayit_sayisi", str(len(kayitlar))),
                ("filtre", json.dumps(FILTRE, ensure_ascii=False, default=lambda v: sorted(v))),
                ("kaynak_klasor", str(GIRDI.relative_to(ROOT))),
            ])
            db.commit()
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("Veri doğrulama başarısız")
        # ayni klasore kopyala, sonra atomik degistir
        yan = CIKTI.with_name(CIKTI.name + ".yeni")
        shutil.copyfile(gecici, yan)
        os.replace(yan, CIKTI)
    finally:
        Path(gecici).unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true", help="yazma, sadece raporla")
    a = ap.parse_args()

    if not GIRDI.exists():
        sys.exit(f"Girdi klasörü yok: {GIRDI}")

    ustveri = hedef_ustverisi()
    if not ustveri:
        sys.exit(f"Araç üstverisi okunamadı: {HEDEFLER}")

    araclar, kayitlar, atlanan = dosyalari_oku(ustveri)
    if not araclar:
        sys.exit("Hiç araç kaydı üretilmedi — filtre fazla dar olabilir.")

    print(f"araç={len(araclar)}  kayıt={len(kayitlar)}")
    for t in TIPLER:
        print(f"  {t:<7} {sum(1 for k in kayitlar if k['tip'] == t)}")
    if atlanan:
        print(f"atlanan dosya: {len(atlanan)}")
        for s in atlanan[:10]:
            print(f"  {s}")

    if a.kuru:
        print("\n--kuru: yazılmadı")
        return
    yaz(araclar, kayitlar)
    print(f"\n-> {CIKTI.relative_to(ROOT)}  ({CIKTI.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
