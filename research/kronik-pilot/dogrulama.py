"""
dogrulama.py — Kayit semasinin TEK dogruluk kaynagi.
runner.py ve ingest.py bu modulu kullanir; kural degisirse tek yerde degisir.
"""
from __future__ import annotations
import json
from pathlib import Path

AZAMI = {"kronik": 8, "iyi": 5, "kotu": 5}
AZAMI_IDDIA = 140


def etiket_setleri(yol: str | Path) -> dict[str, set[str]]:
    d = json.loads(Path(yol).read_text(encoding="utf-8"))
    return {t: set(d[t]) for t in ("kronik", "iyi", "kotu")}


def dogrula(kayitlar, yontem: str, gecerli: dict[str, set[str]]):
    saglam, gecersiz = [], []
    sayac = {"kronik": 0, "iyi": 0, "kotu": 0}
    for k in kayitlar if isinstance(kayitlar, list) else []:
        if not isinstance(k, dict):
            gecersiz.append({"kayit": k, "sebep": "dict degil"}); continue
        tip, etiket = k.get("tip"), k.get("etiket")
        iddia = (k.get("iddia") or "").strip()
        url = (k.get("kaynak_url") or "").strip()
        if tip not in gecerli:
            gecersiz.append({"kayit": k, "sebep": f"gecersiz tip: {tip}"}); continue
        if etiket not in gecerli[tip]:
            gecersiz.append({"kayit": k, "sebep": f"etiket sette yok: {etiket}"}); continue
        if not iddia:
            gecersiz.append({"kayit": k, "sebep": "iddia bos"}); continue
        if len(iddia) > AZAMI_IDDIA:
            gecersiz.append({"kayit": k, "sebep": f"iddia {len(iddia)} karakter (>{AZAMI_IDDIA})"}); continue
        if yontem == "B" and not url:
            gecersiz.append({"kayit": k, "sebep": "B'de kaynak_url zorunlu"}); continue
        if yontem == "A" and url:
            gecersiz.append({"kayit": k, "sebep": "A'da kaynak_url olmamali"}); continue
        if yontem == "B" and not (k.get("kaynak_alinti") or "").strip():
            gecersiz.append({"kayit": k, "sebep": "B'de kaynak_alinti zorunlu"}); continue
        sayac[tip] += 1
        if sayac[tip] > AZAMI[tip]:
            gecersiz.append({"kayit": k, "sebep": f"{tip} azami {AZAMI[tip]} asildi"}); continue
        saglam.append(k)
    return saglam, gecersiz
