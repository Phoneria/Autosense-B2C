"""
build_production_targets.py — Uretim hedef listesi.

Pilot listesinden (build_targets.py) FARKI:
  - Yas filtresi YOK. Butun araclar aday; 2024 model de listede.
  - Secim tek olcute gore: ilan sayisi (en cok ilan verilen motorlar once).
  - Her ilan SADECE en uzun (en spesifik) eslesen kombinasyona sayilir. Yoksa
    "Passat 1.6" kendi ilanlarina ek olarak "Passat 1.6 TDi"ninkileri de sayar;
    hem kapsam sisiyor hem ayni motor icin defalarca kosum yapiliyor.
  - Her hedefe medyan_yil + yas_grubu etiketi yazilir. Kosum bitince
    "hangi yas grubunda kac arac bos dondu" sorusu veriyle cevaplanir;
    kartin gosterilecegi esik varsayimla degil, sonuca bakilarak konur.

Kullanim: python3 build_production_targets.py [adet]     (varsayilan 300)
"""
from __future__ import annotations
import json, re, sqlite3, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent / "targets_production.json"
ADET = int(sys.argv[1]) if len(sys.argv) > 1 else 300
KATEGORILER = {"otomobil", "arazi-suv-pick-up"}
BU_YIL = 2026


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").replace("I", "ı").replace("İ", "i").lower()
    return re.sub(r"\s+", " ", re.sub(r"[\-–—]", " ", s)).strip()


def slug(s: str) -> str:
    s = s.translate(str.maketrans("İIıĞğÜüŞşÖöÇç", "iiiGgUuSsOoCc")).lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def yas_grubu(medyan: int | None) -> str:
    if medyan is None:
        return "bilinmiyor"
    yas = BU_YIL - medyan
    if yas <= 2:  return "0-2-yas"
    if yas <= 5:  return "3-5-yas"
    if yas <= 10: return "6-10-yas"
    return "10-uzeri"


def main() -> None:
    con = sqlite3.connect(f"file:{DATA/'paket_fiyatlari.db'}?mode=ro", uri=True)
    combos = [r for r in con.execute("""
        SELECT DISTINCT category, marka_adi, seri_adi, motor_adi FROM leaves
        WHERE marka_adi IS NOT NULL AND seri_adi IS NOT NULL AND motor_adi IS NOT NULL
    """) if r[0] in KATEGORILER]
    con.close()

    g = sqlite3.connect(f"file:{DATA/'galeri.db'}?mode=ro", uri=True)
    say, yil = Counter(), defaultdict(Counter)
    for mdl, yr in g.execute("SELECT model, year_raw FROM gallery_listings WHERE model IS NOT NULL"):
        say[mdl] += 1
        m = re.search(r"(19|20)\d{2}", yr or "")
        if m:
            yil[mdl][int(m.group(0))] += 1
    g.close()
    toplam_ilan = sum(say.values())

    kova = defaultdict(list)
    for mdl in say:
        kova[norm(mdl)[:4]].append((norm(mdl), mdl))

    # --- her ilan metnini EN UZUN eslesen kombinasyona ata (cift sayim yok) ---
    kombo_n = {}
    for cat, ma, se, mo in combos:
        etiket = f"{ma} {se} {mo}"
        kombo_n[etiket] = (norm(etiket), cat, ma, se, mo)

    atama = defaultdict(list)          # etiket -> [ilan metni]
    for mdl in say:
        nm = norm(mdl)
        en_iyi, en_uzun = None, -1
        for etiket, (n, *_) in kombo_n.items():
            if (nm == n or nm.startswith(n + " ")) and len(n) > en_uzun:
                en_iyi, en_uzun = etiket, len(n)
        if en_iyi:
            atama[en_iyi].append(mdl)

    aday = []
    for etiket, (n, cat, ma, se, mo) in kombo_n.items():
        ornek = atama.get(etiket, [])
        tot = sum(say[m] for m in ornek)
        yc = Counter()
        for m in ornek:
            yc.update(yil[m])
        if not tot:
            continue
        d = sorted(y for y, c in yc.items() for _ in range(c))
        medyan = d[len(d) // 2] if d else None
        aday.append({
            "id": slug(etiket), "kategori": cat,
            "marka": ma, "seri": se, "motor": mo, "etiket": etiket,
            "yil_araligi": [d[int(len(d)*0.10)], d[int(len(d)*0.90)-1]] if d else None,
            "medyan_yil": medyan, "yas_grubu": yas_grubu(medyan),
            "ilan_sayisi": tot, "ornek_ilan_metinleri": sorted(ornek)[:5],
        })

    aday.sort(key=lambda c: (-c["ilan_sayisi"], c["etiket"]))
    hedefler = aday[:ADET]
    for i, h in enumerate(hedefler, 1):
        h["sira"] = i

    OUT.write_text(json.dumps({
        "surum": 1,
        "secim_kurali": {
            "olcut": "ilan_sayisi (azalan)", "adet": ADET,
            "kategoriler": sorted(KATEGORILER),
            "yas_filtresi": None,
            "not": "Yas filtresi bilerek yok. yas_grubu sadece etiket; secimi etkilemez.",
        },
        "hedefler": hedefler,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    kaps = sum(h["ilan_sayisi"] for h in hedefler)
    print(f"Aday kombinasyon: {len(aday)}   secilen: {len(hedefler)}")
    print(f"Kapsam: {kaps:,} / {toplam_ilan:,} ilan  (%{100*kaps/toplam_ilan:.1f})")
    print(f"En dusuk ilan sayisi (300. sira): {hedefler[-1]['ilan_sayisi']}\n")
    gr = Counter(h["yas_grubu"] for h in hedefler)
    print(f"{'yas grubu':<14}{'motor':>7}{'ilan':>10}")
    for k in ("0-2-yas", "3-5-yas", "6-10-yas", "10-uzeri", "bilinmiyor"):
        if gr[k]:
            il = sum(h["ilan_sayisi"] for h in hedefler if h["yas_grubu"] == k)
            print(f"{k:<14}{gr[k]:>7}{il:>10,}")
    print(f"\nIlk 10: " + " | ".join(h["etiket"] for h in hedefler[:10]))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
