"""ingest.py — ham ajan ciktilarini dogrular, ciktilar/<yontem>/<id>__<model>.json yazar."""
from __future__ import annotations
import json, sys
from pathlib import Path
from dogrulama import dogrula, etiket_setleri

BURADA = Path(__file__).resolve().parent
ETIKET = etiket_setleri("/mnt/user-data/uploads/Autosense-B2C/research/kronik-pilot/etiketler.json")
MODEL = sys.argv[1] if len(sys.argv) > 1 else "claude-opus-5"

ozet = {}
for yontem in ("A", "B"):
    hedefd = BURADA / "ciktilar" / yontem
    hedefd.mkdir(parents=True, exist_ok=True)
    s_top = g_top = 0
    for yol in sorted((BURADA / "ham" / yontem).glob("*.json")):
        veri = json.loads(yol.read_text(encoding="utf-8"))
        saglam, gecersiz = dogrula(veri.get("kayitlar", []), yontem, ETIKET)
        (hedefd / f"{yol.stem}__{MODEL}.json").write_text(json.dumps({
            "hedef_id": veri.get("hedef_id", yol.stem), "yontem": yontem, "model": MODEL,
            "kayitlar": saglam, "_gecersiz": gecersiz,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        s_top += len(saglam); g_top += len(gecersiz)
        if gecersiz:
            for g in gecersiz:
                print(f"  [{yontem}] {yol.stem}: {g['sebep']}")
    ozet[yontem] = (s_top, g_top)

print()
for y, (s, g) in ozet.items():
    print(f"{y}: {s} gecerli kayit, {g} sema ihlali")
