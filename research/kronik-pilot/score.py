"""
score.py — Elle doldurulmus degerlendirme.csv'yi okur, objektif sayilari basar.

LLM puanlamasi YOK. Tum kararlar insan tarafindan verilmis sabit kodlardan okunur:
  KARAR           : D = dogrulandi | Y = yanlis | K = teyit edilemedi
  URL_ACILIYOR    : E | H   (yalniz B icin; bos ise atlanir)
  URL_DESTEKLIYOR : E | H   (yalniz B icin; bos ise atlanir)
"""
from __future__ import annotations
import csv
from collections import Counter, defaultdict
from pathlib import Path

CSV = Path(__file__).resolve().parent / "degerlendirme.csv"
GECERLI = {"D", "Y", "K"}


def yuzde(pay: int, payda: int) -> str:
    return f"%{100*pay/payda:.1f}" if payda else "  -  "


def main() -> None:
    if not CSV.exists():
        print("degerlendirme.csv yok. Once make_sheet.py calistir ve KARAR sutununu doldur.")
        return

    satir = [r for r in csv.DictReader(CSV.open(encoding="utf-8-sig"))]
    dolu = [r for r in satir if (r.get("KARAR") or "").strip().upper() in GECERLI]
    eksik = len(satir) - len(dolu)

    print(f"Toplam iddia: {len(satir)}   Degerlendirilmis: {len(dolu)}   Bos: {eksik}\n")
    if not dolu:
        return

    print("=" * 62)
    print(f"{'yontem/katman':<26}{'n':>5}{'dogru':>10}{'YANLIS':>10}{'teyitsiz':>11}")
    print("=" * 62)
    gruplar: dict[tuple, Counter] = defaultdict(Counter)
    for r in dolu:
        k = r["KARAR"].strip().upper()
        gruplar[(r["yontem"], r["katman"])][k] += 1
        gruplar[(r["yontem"], "TUMU")][k] += 1

    for anahtar in sorted(gruplar):
        c = gruplar[anahtar]
        n = sum(c.values())
        ad = f"{anahtar[0]} / {anahtar[1]}"
        vurgu = "  <<<" if anahtar[1] == "TUMU" else ""
        print(f"{ad:<26}{n:>5}{yuzde(c['D'],n):>10}{yuzde(c['Y'],n):>10}{yuzde(c['K'],n):>11}{vurgu}")

    # --- B'ye ozel: URL saglamligi ---
    b_url = [r for r in dolu if r["yontem"] == "B" and (r.get("kaynak_url") or "").strip()]
    acik = [r for r in b_url if (r.get("URL_ACILIYOR") or "").strip().upper() in {"E", "H"}]
    if acik:
        olu = sum(1 for r in acik if r["URL_ACILIYOR"].strip().upper() == "H")
        print(f"\nB — kontrol edilen URL: {len(acik)}   acilmayan/uydurma: {olu} ({yuzde(olu,len(acik))})")
        dest = [r for r in acik if (r.get("URL_DESTEKLIYOR") or "").strip().upper() in {"E", "H"}]
        if dest:
            yok = sum(1 for r in dest if r["URL_DESTEKLIYOR"].strip().upper() == "H")
            print(f"B — URL aciliyor ama iddiayi desteklemiyor: {yok} ({yuzde(yok,len(dest))})")

    # --- guven kalibrasyonu: 'yuksek' dedigi yerde ne kadar yaniliyor ---
    print("\nGuven kalibrasyonu (yanlis orani):")
    for yontem in ("A", "B"):
        for g in ("yuksek", "orta", "dusuk"):
            alt = [r for r in dolu if r["yontem"] == yontem and r.get("guven") == g]
            if alt:
                y = sum(1 for r in alt if r["KARAR"].strip().upper() == "Y")
                print(f"  {yontem} / {g:<7} n={len(alt):<4} yanlis {yuzde(y,len(alt))}")

    # --- iddia tipine gore ---
    print("\nIddia tipine gore yanlis orani:")
    for yontem in ("A", "B"):
        for t in ("kronik", "iyi", "kotu"):
            alt = [r for r in dolu if r["yontem"] == yontem and r.get("tip") == t]
            if alt:
                y = sum(1 for r in alt if r["KARAR"].strip().upper() == "Y")
                print(f"  {yontem} / {t:<7} n={len(alt):<4} yanlis {yuzde(y,len(alt))}")


if __name__ == "__main__":
    main()
