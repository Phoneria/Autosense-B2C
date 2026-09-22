"""
ingest_uretim.py — ham_uretim/B ciktilarini dogrular ve ciktilar_uretim/B'ye yazar.
Her parti bittikten sonra calistir. Idempotent; tekrar calistirmak zarar vermez.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from dogrulama import dogrula, etiket_setleri

B = Path(__file__).resolve().parent
MODEL_VARSAYILAN = "claude-opus-5"  # ham JSON'da "model" alani yoksa kullanilir (geriye donuk uyumluluk)
ET = etiket_setleri(B / "etiketler.json")
out = B / "ciktilar_uretim" / "B"; out.mkdir(parents=True, exist_ok=True)

tot, dom, bos, ihlal = Counter(), Counter(), [], []
bitti = []
for p in sorted((B / "ham_uretim" / "B").glob("*.json")):
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        ihlal.append(f"{p.stem}: JSON bozuk ({e})"); continue
    model = v.get("model") or MODEL_VARSAYILAN
    s, g = dogrula(v.get("kayitlar", []), "B", ET)
    (out / f"{p.stem}__{model}.json").write_text(json.dumps(
        {"hedef_id": v.get("hedef_id", p.stem), "yontem": "B", "model": model,
         "kayitlar": s, "_gecersiz": g}, ensure_ascii=False, indent=2), encoding="utf-8")
    bitti.append(p.stem)
    if not s: bos.append(p.stem)
    for x in g: ihlal.append(f"{p.stem}: {x['sebep']}")
    for k in s:
        tot[k["tip"]] += 1
        if k.get("kaynak_url"): dom[urlparse(k["kaynak_url"]).netloc] += 1

(B / "ciktilar_uretim" / "_durum.json").write_text(json.dumps(
    {"tamamlanan_hedefler": bitti, "kayit_sayilari": dict(tot)}, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"hedef={len(bitti)}  kronik={tot['kronik']} iyi={tot['iyi']} kotu={tot['kotu']} "
      f"toplam={sum(tot.values())}  sema_ihlali={len(ihlal)}  bos_hedef={len(bos)}")
if ihlal: print("ihlaller:\n  " + "\n  ".join(ihlal[:15]))
if bos:   print("bos donen hedefler: " + ", ".join(bos))
print(f"farkli alan adi={len(dom)} | ilk5: " + ", ".join(f"{d}({n})" for d, n in dom.most_common(5)))
