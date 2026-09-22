"""
render_prompts.py — Henuz kosulmamis hedefler icin hazir prompt dosyasi uretir.

  python3 render_prompts.py            # sirada bekleyen ilk 13 hedef
  python3 render_prompts.py 25         # sirada bekleyen ilk 25 hedef
  python3 render_prompts.py 13 --liste # sadece listele, dosya yazma

Tamamlanmis hedefler (ham_uretim/B icinde .json'i olanlar) atlanir.
Cikti: rendered_uretim/<id>.md
"""
from __future__ import annotations
import json, sys
from pathlib import Path

B = Path(__file__).resolve().parent
ADET = next((int(a) for a in sys.argv[1:] if a.isdigit() and int(a) > 0), 13)
SADECE_LISTE = "--liste" in sys.argv

etiket = json.loads((B / "etiketler.json").read_text(encoding="utf-8"))
etj = json.dumps({t: etiket[t] for t in ("kronik", "iyi", "kotu")}, ensure_ascii=False, indent=2)
sablon = (B / "prompt_B_kaynakli.md").read_text(encoding="utf-8")
hedefler = json.loads((B / "targets_production.json").read_text(encoding="utf-8"))["hedefler"]

bitti = {p.stem for p in (B / "ham_uretim" / "B").glob("*.json")}
sirada = [h for h in hedefler if h["id"] not in bitti][:ADET]

if not sirada:
    print("Sirada hedef yok — 300'un hepsi tamam."); sys.exit()

cikti = B / "rendered_uretim"; cikti.mkdir(exist_ok=True)
for h in sirada:
    if not SADECE_LISTE:
        girdi = {k: h[k] for k in ("id", "marka", "seri", "motor", "etiket", "yil_araligi")}
        (cikti / f"{h['id']}.md").write_text(
            sablon.replace("{{ETIKETLER}}", etj).replace("{{HEDEF}}", json.dumps(girdi, ensure_ascii=False, indent=2)),
            encoding="utf-8")
    print(f"{h['sira']:>4}  {h['id']:<42} {h['ilan_sayisi']:>6} ilan  {h['yas_grubu']}")

print(f"\nToplam {len(hedefler)} hedef | bitti {len(bitti)} | kalan {len(hedefler)-len(bitti)}")
if not SADECE_LISTE:
    print(f"Prompt dosyalari hazir: rendered_uretim/")
