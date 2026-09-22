"""
runner.py — A ve B promptlarini 20 hedef uzerinde kosturur, ciktilari kaydeder.

KRITIK: A ve B ayni kod yolundan gecer. Tek fark `tools` alani —
A'da bos, B'de web_search. Baska bir fark testi gecersiz kilar.

Kullanim:
    export OPENAI_API_KEY=sk-...
    python3 runner.py                 # ikisini de, eksik olanlari
    python3 runner.py --yontem B      # sadece B
    python3 runner.py --limit 3       # ilk 3 hedef (deneme)
    python3 runner.py --yeniden       # var olan ciktilarin uzerine yaz
    python3 runner.py --model gpt-5.5

Ag erisimi: api.openai.com'a cikis gerekir. Bu betigi kendi terminalinden
calistirmak en garantisi.
"""
from __future__ import annotations
import argparse, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

BURADA = Path(__file__).resolve().parent
UC = "https://api.openai.com/v1/responses"
VARSAYILAN_MODEL = os.environ.get("PILOT_MODEL", "gpt-6-astra")

PROMPT_DOSYASI = {"A": "prompt_A_kapali_kitap.md", "B": "prompt_B_kaynakli.md"}
from dogrulama import dogrula as _dogrula, etiket_setleri

ETIKETLER = json.loads((BURADA / "etiketler.json").read_text(encoding="utf-8"))
GECERLI_ETIKET = etiket_setleri(BURADA / "etiketler.json")


def dogrula(kayitlar: list, yontem: str):
    """Sema kurallari dogrulama.py'de; runner ve ingest ayni kurali kullansin."""
    return _dogrula(kayitlar, yontem, GECERLI_ETIKET)


# ------------------------------------------------------------------------- akis
def prompt_kur(yontem: str, hedef: dict) -> str:
    ham = (BURADA / PROMPT_DOSYASI[yontem]).read_text(encoding="utf-8")
    girdi = {k: hedef[k] for k in ("id", "marka", "seri", "motor", "etiket", "yil_araligi")}
    return (ham
            .replace("{{ETIKETLER}}", json.dumps(
                {t: ETIKETLER[t] for t in ("kronik", "iyi", "kotu")}, ensure_ascii=False, indent=2))
            .replace("{{HEDEF}}", json.dumps(girdi, ensure_ascii=False, indent=2)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yontem", choices=["A", "B", "AB"], default="AB")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=VARSAYILAN_MODEL)
    ap.add_argument("--yeniden", action="store_true")
    a = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY tanimli degil.")

    hedefler = json.loads((BURADA / "targets_pilot.json").read_text(encoding="utf-8"))["hedefler"]
    if a.limit:
        hedefler = hedefler[:a.limit]
    yontemler = ["A", "B"] if a.yontem == "AB" else [a.yontem]

    ozet = {y: {"kayit": 0, "gecersiz": 0, "url_teyitsiz": 0, "hata": 0} for y in yontemler}

    for yontem in yontemler:
        klasor = BURADA / "ciktilar" / yontem
        klasor.mkdir(parents=True, exist_ok=True)
        for i, h in enumerate(hedefler, 1):
            cikti = klasor / f"{h['id']}.json"
            if cikti.exists() and not a.yeniden:
                print(f"[{yontem} {i}/{len(hedefler)}] {h['etiket']} — atlandi (var)")
                continue
            print(f"[{yontem} {i}/{len(hedefler)}] {h['etiket']} ...", flush=True)
            try:
                yanit = cagir(prompt_kur(yontem, h), a.model, arama=(yontem == "B"))
            except Exception as e:
                print(f"    HATA: {e}")
                ozet[yontem]["hata"] += 1
                continue

            metin, arac_url = metin_ve_kaynaklar(yanit)
            cozum = json_ayikla(metin)
            if not cozum:
                print("    HATA: JSON ayristirilamadi")
                (klasor / f"{h['id']}.ham.txt").write_text(metin, encoding="utf-8")
                ozet[yontem]["hata"] += 1
                continue

            saglam, gecersiz = dogrula(cozum.get("kayitlar", []), yontem)

            # Otomatik sinyal: model'in yazdigi URL, aracin gercekten getirdigi
            # URL'ler arasinda mi? Degilse buyuk ihtimalle uydurma.
            teyitsiz = 0
            if yontem == "B":
                kok = {u.split("//")[-1].split("/")[0] for u in arac_url}
                for k in saglam:
                    u = (k.get("kaynak_url") or "")
                    k["_arac_sonucunda_var"] = bool(u) and u.split("//")[-1].split("/")[0] in kok
                    teyitsiz += 0 if k["_arac_sonucunda_var"] else 1

            cikti.write_text(json.dumps({
                "hedef_id": h["id"], "yontem": yontem, "model": a.model,
                "kayitlar": saglam,
                "_gecersiz": gecersiz,
                "_arac_getirdigi_urller": arac_url,
            }, ensure_ascii=False, indent=2), encoding="utf-8")

            ozet[yontem]["kayit"] += len(saglam)
            ozet[yontem]["gecersiz"] += len(gecersiz)
            ozet[yontem]["url_teyitsiz"] += teyitsiz
            ek = f", arac disi URL {teyitsiz}" if yontem == "B" else ""
            print(f"    {len(saglam)} kayit, {len(gecersiz)} gecersiz{ek}")

    print("\n--- ozet ---")
    for y, s in ozet.items():
        print(f"{y}: {s['kayit']} kayit, {s['gecersiz']} sema ihlali, "
              f"{s['url_teyitsiz']} arac disi URL, {s['hata']} hata")
    print("\nSirada: python3 make_sheet.py")


if __name__ == "__main__":
    main()
