"""
build_targets.py — Kronik/artı-eksi pilotu için hedef model listesi üretir.

Girdi : data/paket_fiyatlari.db (yapisal marka/seri/motor), data/galeri.db (ilan frekansi)
Cikti : research/kronik-pilot/targets_pilot.json

Secim kurali (deterministik, rastgelelik yok):
  - Her iki katmanda da medyan ilan yili <= MAX_MEDYAN_YIL. Gerekcesi: 2-3 yasindaki
    bir aracin kronigi HENUZ OLUSMAMISTIR; onu listeye koymak testi bozar, cunku
    dogru cevap "bilinmiyor"dur ve bunu ne LLM ne usta bilebilir.
  - populer    : ilan sayisina gore en ustten, her marka+seri'den en fazla 1 tane
  - uzun-kuyruk: ilan sayisi UZUN_KUYRUK_ARALIK icinde, sayaca gore ESIT ARALIKLI
    dagitilarak (hepsi ustte kumelenmesin), her markadan en fazla 1 tane
"""
from __future__ import annotations
import json, re, sqlite3, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent / "targets_pilot.json"

POPULER_ADET = 10
KUYRUK_ADET = 10
UZUN_KUYRUK_ARALIK = (5, 150)      # ilan sayisi bu araliktakiler "uzun kuyruk"
MAX_MEDYAN_YIL = 2020             # daha yeni araclarin kronigi henuz olusmamistir
KATEGORILER = {"otomobil", "arazi-suv-pick-up"}   # ticari/panelvan pilotta yok


def norm(s: str) -> str:
    """Eslestirme icin normalize: kucuk harf, Turkce harfler sadelestirilmez,
    tire ve fazla bosluklar tek bosluga iner."""
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("I", "ı").replace("İ", "i").lower()
    s = re.sub(r"[\-–—]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def slug(s: str) -> str:
    """Dosya adi / id icin ASCII-guvenli kisaltma. norm() eslestirme icindir ve
    Turkce kurala gore I -> i yapar; id'de bunu istemiyoruz (GTI -> gtı olurdu)."""
    esle = str.maketrans("İIıĞğÜüŞşÖöÇç", "iiiGgUuSsOoCc")
    s = s.translate(esle).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def load_combos() -> list[dict]:
    con = sqlite3.connect(f"file:{DATA/'paket_fiyatlari.db'}?mode=ro", uri=True)
    rows = con.execute("""
        SELECT DISTINCT category, marka_adi, seri_adi, motor_adi
        FROM leaves
        WHERE marka_adi IS NOT NULL AND seri_adi IS NOT NULL AND motor_adi IS NOT NULL
    """).fetchall()
    con.close()
    out = []
    for cat, marka, seri, motor in rows:
        if cat not in KATEGORILER:
            continue
        etiket = f"{marka} {seri} {motor}".strip()
        out.append({
            "kategori": cat, "marka": marka, "seri": seri, "motor": motor,
            "etiket": etiket, "_n": norm(etiket),
        })
    return out


def load_listing_stats() -> dict[str, dict]:
    """Her farkli 'model' metni icin ilan sayisi + yil dagilimi."""
    con = sqlite3.connect(f"file:{DATA/'galeri.db'}?mode=ro", uri=True)
    say: Counter = Counter()
    yillar: dict[str, Counter] = defaultdict(Counter)
    for model, year_raw in con.execute(
        "SELECT model, year_raw FROM gallery_listings WHERE model IS NOT NULL"
    ):
        say[model] += 1
        m = re.search(r"(19|20)\d{2}", year_raw or "")
        if m:
            yillar[model][int(m.group(0))] += 1
    con.close()
    return {m: {"adet": n, "yillar": yillar[m]} for m, n in say.items()}


def medyan_yil(sayac: Counter) -> int | None:
    if not sayac:
        return None
    diz = sorted(y for y, n in sayac.items() for _ in range(n))
    return diz[len(diz) // 2]


def yil_araligi(sayac: Counter) -> list[int] | None:
    """Ilan yillarinin %10-%90 dilimi — uc degerleri disarida birakir."""
    if not sayac:
        return None
    diz = sorted(y for y, n in sayac.items() for _ in range(n))
    if not diz:
        return None
    alt = diz[int(len(diz) * 0.10)]
    ust = diz[int(len(diz) * 0.90) - 1 if len(diz) > 1 else 0]
    return [alt, ust]


def esle(combos: list[dict], stats: dict[str, dict]) -> list[dict]:
    """Her kombinasyonu, o metinle BASLAYAN ilan model metinleriyle eslestirir."""
    kova: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for model in stats:
        n = norm(model)
        kova[n[:4]].append((n, model))

    for c in combos:
        n = c["_n"]
        toplam = 0
        yil = Counter()
        ornekler = []
        for nm, model in kova.get(n[:4], ()):
            if nm == n or nm.startswith(n + " "):
                toplam += stats[model]["adet"]
                yil.update(stats[model]["yillar"])
                ornekler.append(model)
        c["ilan_sayisi"] = toplam
        c["yil_araligi"] = yil_araligi(yil)
        c["medyan_yil"] = medyan_yil(yil)
        c["eslesen_ilan_metinleri"] = sorted(ornekler)[:5]
    return combos


def sec(combos: list[dict]) -> tuple[list[dict], list[dict]]:
    uygun = [c for c in combos
             if c["ilan_sayisi"] > 0 and c["yil_araligi"]
             and c["medyan_yil"] and c["medyan_yil"] <= MAX_MEDYAN_YIL]
    uygun.sort(key=lambda c: (-c["ilan_sayisi"], c["etiket"]))

    populer, gorulen_seri = [], set()
    for c in uygun:
        anahtar = (c["marka"], c["seri"])
        if anahtar in gorulen_seri:
            continue
        gorulen_seri.add(anahtar)
        populer.append(c)
        if len(populer) == POPULER_ADET:
            break

    alt, ust = UZUN_KUYRUK_ARALIK
    aday = [c for c in uygun if alt <= c["ilan_sayisi"] <= ust]
    # esit araliklarla ornekle: hepsi ust sinirda kumelenmesin
    if len(aday) > KUYRUK_ADET * 4:
        adim = len(aday) / (KUYRUK_ADET * 4)
        aday = [aday[int(i * adim)] for i in range(KUYRUK_ADET * 4)]
    kuyruk, gorulen_marka = [], set()
    for c in aday:
        if c["marka"] in gorulen_marka:
            continue
        gorulen_marka.add(c["marka"])
        kuyruk.append(c)
        if len(kuyruk) == KUYRUK_ADET:
            break
    return populer, kuyruk


def main() -> None:
    combos = esle(load_combos(), load_listing_stats())
    populer, kuyruk = sec(combos)

    def temizle(c: dict, katman: str) -> dict:
        return {
            "id": slug(c["etiket"]),
            "katman": katman,
            "kategori": c["kategori"],
            "marka": c["marka"], "seri": c["seri"], "motor": c["motor"],
            "etiket": c["etiket"],
            "yil_araligi": c["yil_araligi"],
            "medyan_yil": c["medyan_yil"],
            "ilan_sayisi": c["ilan_sayisi"],
            "ornek_ilan_metinleri": c["eslesen_ilan_metinleri"],
        }

    hedefler = ([temizle(c, "populer") for c in populer]
                + [temizle(c, "uzun-kuyruk") for c in kuyruk])
    OUT.write_text(json.dumps({
        "surum": 1,
        "secim_kurali": {
            "populer_adet": POPULER_ADET, "kuyruk_adet": KUYRUK_ADET,
            "uzun_kuyruk_ilan_araligi": list(UZUN_KUYRUK_ARALIK),
            "max_medyan_yil": MAX_MEDYAN_YIL,
            "kategoriler": sorted(KATEGORILER),
        },
        "hedefler": hedefler,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    for h in hedefler:
        print(f"{h['katman']:12} {h['ilan_sayisi']:6}  {h['etiket']}  {h['yil_araligi']}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
