"""
make_sheet.py — Model ciktilarini tek bir elle-doldurulacak CSV'ye cevirir.

Girdi : ciktilar/A/<hedef_id>.json, ciktilar/B/<hedef_id>.json
Cikti : degerlendirme.csv   (KARAR / URL_ACILIYOR / URL_DESTEKLIYOR sutunlari BOS)

Satirlar KARISIK sirada yazilir ve 'yontem' sutunu en sona konur; degerlendirmeyi
yapan kisi A mi B mi oldugunu bilmeden karar versin diye. (Kor degerlendirme.)
Puanlama sirasinda score.py yontemi yine de okur.
"""
from __future__ import annotations
import csv, hashlib, json, sys
from pathlib import Path

# Bu turda sadece kronik iddialar elle degerlendiriliyor: risk orada.
# "bagaji kucuk" yanlissa kimse zarar gormez, "sanzimani patlar" yanlissa urun yanar.
# iyi/kotu kayitlari yine uretiliyor, sadece bu CSV'ye girmiyor.
# Hepsini almak icin:  python3 make_sheet.py --hepsi
DEGERLENDIRILEN_TIPLER = {"kronik"}

BURADA = Path(__file__).resolve().parent
CIKTILAR = BURADA / "ciktilar"
HEDEFLER = json.loads((BURADA / "targets_pilot.json").read_text(encoding="utf-8"))["hedefler"]
KATMAN = {h["id"]: h["katman"] for h in HEDEFLER}
ETIKET = {h["id"]: h["etiket"] for h in HEDEFLER}

SUTUNLAR = [
    "satir_id", "arac", "tip", "etiket", "iddia", "km_araligi", "guven",
    "kaynak_url", "kaynak_alinti",
    "KARAR", "URL_ACILIYOR", "URL_DESTEKLIYOR", "NOT",
    "katman", "yontem", "hedef_id",
]


TIPLER: set[str] = DEGERLENDIRILEN_TIPLER


def satirlar() -> list[dict]:
    out = []
    for yontem in ("A", "B"):
        for yol in sorted((CIKTILAR / yontem).glob("*.json")):
            veri = json.loads(yol.read_text(encoding="utf-8"))
            hid = veri.get("hedef_id", yol.stem)
            for k in veri.get("kayitlar", []):
                if TIPLER and k.get("tip") not in TIPLER:
                    continue
                out.append({
                    "arac": ETIKET.get(hid, hid),
                    "tip": k.get("tip", ""),
                    "etiket": k.get("etiket", ""),
                    "iddia": k.get("iddia", ""),
                    "km_araligi": k.get("km_araligi") or "",
                    "guven": k.get("guven", ""),
                    "kaynak_url": k.get("kaynak_url") or "",
                    "kaynak_alinti": k.get("kaynak_alinti") or "",
                    "KARAR": "", "URL_ACILIYOR": "", "URL_DESTEKLIYOR": "", "NOT": "",
                    "katman": KATMAN.get(hid, "?"),
                    "yontem": yontem,
                    "hedef_id": hid,
                })
    # deterministik ama yontemden bagimsiz karisik sira (kor degerlendirme)
    for s in out:
        tohum = f"{s['hedef_id']}|{s['tip']}|{s['etiket']}|{s['iddia']}"
        s["satir_id"] = hashlib.sha1(tohum.encode()).hexdigest()[:8]
    out.sort(key=lambda s: s["satir_id"])
    return out


def main() -> None:
    global TIPLER
    TIPLER = set() if "--hepsi" in sys.argv else DEGERLENDIRILEN_TIPLER
    kayit = satirlar()
    if not kayit:
        print("ciktilar/A ve ciktilar/B bos — once model ciktilarini oraya koy.")
        return
    hedef = BURADA / "degerlendirme.csv"
    with hedef.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SUTUNLAR)
        w.writeheader()
        w.writerows(kayit)
    a = sum(1 for s in kayit if s["yontem"] == "A")
    kapsam = "tum tipler" if not TIPLER else "+".join(sorted(TIPLER))
    print(f"{len(kayit)} iddia yazildi (A={a}, B={len(kayit)-a}) [{kapsam}] -> {hedef}")


if __name__ == "__main__":
    main()
