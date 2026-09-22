#!/usr/bin/env python3
"""Explicit, read-only source import; account tables and secrets are never copied."""
import argparse
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def snapshot(source, destination, tables=()):
    source = source.resolve(strict=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(suffix=".sqlite3", dir=destination.parent)
    os.close(fd)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
            with sqlite3.connect(temporary) as dst:
                if tables:
                    # Only the fixed analysis allowlist can be imported.
                    assert set(tables) <= {"search_listing", "galleries", "gallery_listings"}
                    for table in tables:
                        ddl = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                        if not ddl:
                            raise RuntimeError(f"{table} tablosu bulunamadı")
                        dst.execute(ddl[0])
                        rows = src.execute(f'SELECT * FROM "{table}" NOT INDEXED')
                        placeholders = ",".join("?" for _ in rows.description)
                        dst.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
                    if "search_listing" in tables:
                        dst.execute('CREATE INDEX b2c_listing_brand_year ON search_listing(brand, year)')
                    if "gallery_listings" in tables:
                        dst.execute('CREATE INDEX b2c_gallery_snapshot ON gallery_listings(snapshot_date)')
                        dst.execute('CREATE INDEX b2c_gallery_model ON gallery_listings(model, snapshot_date)')
                        dst.execute('ANALYZE gallery_listings')
                else:
                    src.backup(dst, pages=4096)
                dst.commit()
                check = dst.execute("PRAGMA quick_check").fetchone()[0]
                if check != "ok":
                    raise RuntimeError(f"Veri doğrulama başarısız: {check}")
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Autosense kaynak klasörü")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    targets = [
        (source / "Backend/db.sqlite3", ROOT / "data/listings.sqlite3", ("search_listing",)),
        (source / "Arabam Otomasyon/paket_fiyatlari.db", ROOT / "data/paket_fiyatlari.db", ()),
        (source / "Galeri/galeri.db", ROOT / "data/galeri.db", ("galleries", "gallery_listings")),
    ]
    for src, dst, table in targets:
        print(f"Salt okunur kopya hazırlanıyor: {dst.name}", flush=True)
        snapshot(src, dst, table)
    (ROOT / "data/import.json").write_text(json.dumps({
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "files": [dst.name for _, dst, _ in targets],
        "note": "Bağımsız snapshot; otomatik senkronizasyon yok. B2B hesapları taşınmadı.",
    }, ensure_ascii=False, indent=2) + "\n")
    print("Kopyalama tamamlandı. Veri yenilendiğinde çalışan B2C servisini yeniden başlatın.")


if __name__ == "__main__":
    main()
