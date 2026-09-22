"""galeri.db yerine kullanılan küçültülmüş özet veri kaynağı.

Eskiden b2c.py, 1.8 GB'lık `galeri.db`'ye (1,6M satırlık günlük galeri
snapshot'u) her analizde SQL sorgusu atıyordu. `scripts/build_galeri_summary.py`
o veriyi bir kerede (marka, seri, yıl) bazında özetleyip iki küçük JSON'a
indirger:

  * data/galeri_summary.json          — grup başına medyan/p25/p75 fiyat,
    şehir ortalamaları, renk fiyat faktörü, haftalık fiyat trendi.
  * data/galeri_latest_snapshot.json   — en son güne ait canlı ilanlar
    ("benzer ilan" kartı için — gerçek URL/galeri gerekiyor, özet yetmez).

Bu modül o iki dosyayı RAM'de (mtime ile) cache'ler; disk I/O sadece dosya
gerçekten değiştiğinde olur. Kaynak `galeri.db` artık production sunucusunda
tutulmuyor — üretim script'i ayrı bir yerde (indirilen/işlenen makinede)
çalıştırılıp sadece bu iki JSON deploy ediliyor.
"""

from __future__ import annotations

import json
import os
import threading

from django.conf import settings

_lock = threading.Lock()
_summary_cache: dict = {"key": None, "data": None}
_snapshot_cache: dict = {"key": None, "data": None}

_EMPTY_SUMMARY: dict = {"groups": {}}
_EMPTY_SNAPSHOT: dict = {"snapshot_date": None, "listings": []}


def _file_key(path: str):
    try:
        return (path, os.stat(path).st_mtime_ns)
    except OSError:
        return (path, None)


def _load(setting_name: str, cache_slot: dict, default: dict) -> dict:
    path = str(getattr(settings, setting_name))
    key = _file_key(path)
    if cache_slot["key"] == key and cache_slot["data"] is not None:
        return cache_slot["data"]
    with _lock:
        if cache_slot["key"] != key or cache_slot["data"] is None:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                data = default
            cache_slot["data"] = data
            cache_slot["key"] = key
        return cache_slot["data"]


def summary() -> dict:
    """Tam `galeri_summary.json` içeriği (`groups`: "{marka}|{seri}|{yıl}" -> özet)."""
    return _load("B2C_GALERI_SUMMARY", _summary_cache, _EMPTY_SUMMARY)


def latest_snapshot() -> dict:
    """Tam `galeri_latest_snapshot.json` içeriği (`listings`: güncel ilan listesi)."""
    return _load("B2C_GALERI_LATEST_SNAPSHOT", _snapshot_cache, _EMPTY_SNAPSHOT)


def groups_for(brand: str, series: str, year: int, tolerance: int = 1) -> list[dict]:
    """(marka, seri, yıl±tolerans) ile eşleşen özet gruplarının listesi."""
    groups = summary().get("groups") or {}
    out = []
    for y in range(year - tolerance, year + tolerance + 1):
        g = groups.get(f"{brand}|{series}|{y}")
        if g:
            out.append(g)
    return out
