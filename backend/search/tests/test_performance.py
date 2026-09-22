import json
from unittest.mock import patch

import pytest
from django.core.cache import cache

from search.services import b2c, galeri_summary
from search.services.arabam_vehicles_service import load_arabam_vehicles


@pytest.fixture
def galeri_files(tmp_path, settings):
    """galeri.db yerine geçen iki küçük JSON'un sahte (küçük) hâli. Gerçek
    scripts/build_galeri_summary.py çıktısıyla aynı şemayı kullanır."""
    summary_path = tmp_path / "galeri_summary.json"
    snapshot_path = tmp_path / "galeri_latest_snapshot.json"

    summary_data = {
        "groups": {
            "Fiat|Egea|2019": {
                "brand": "Fiat", "series": "Egea", "year": 2019,
                "sample_count": 100, "unique_vehicles": 40, "unique_sellers": 15,
                "median_price": 800_000, "p25": 700_000, "p75": 900_000,
                "latest_date": "2026-09-20",
                "cities": {
                    "istanbul": {"avg_price": 820_000, "count": 40},
                    "ankara": {"avg_price": 760_000, "count": 20},
                },
                "colors": {
                    "beyaz": {"factor_pct": 2.0, "sample_count": 30},
                    "kirmizi": {"factor_pct": -5.0, "sample_count": 10},
                },
                "price_trend": [
                    {"week": "2026-W36", "avg_price": 790_000, "count": 50},
                    {"week": "2026-W37", "avg_price": 800_000, "count": 50},
                ],
            },
            "Fiat|Egea|2020": {
                "brand": "Fiat", "series": "Egea", "year": 2020,
                "sample_count": 60, "unique_vehicles": 25, "unique_sellers": 10,
                "median_price": 900_000, "p25": 820_000, "p75": 980_000,
                "latest_date": "2026-09-21",
                "cities": {"istanbul": {"avg_price": 910_000, "count": 30}},
                "colors": {"beyaz": {"factor_pct": 1.0, "sample_count": 20}},
                "price_trend": [{"week": "2026-W37", "avg_price": 900_000, "count": 30}],
            },
        }
    }
    snapshot_data = {
        "snapshot_date": "2026-09-22",
        "listings": [
            {
                "brand": "Fiat", "series": "Egea", "year": 2019,
                "title": "Fiat Egea 1.4 Easy", "km": 45000.0, "color": "Beyaz",
                "price": 810_000, "url": "https://example.com/1",
                "city": "İstanbul", "district": "Kadıköy",
                "gallery": "Test Galeri", "post_age_days": 3,
            },
            {
                "brand": "Fiat", "series": "Egea", "year": 2020,
                "title": "Fiat Egea 1.6 Elegance", "km": 20000.0, "color": "Kırmızı",
                "price": 950_000, "url": "https://example.com/2",
                "city": "Ankara", "district": "Çankaya",
                "gallery": "Başka Galeri", "post_age_days": 1,
            },
        ],
    }
    summary_path.write_text(json.dumps(summary_data), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot_data), encoding="utf-8")
    settings.B2C_GALERI_SUMMARY = str(summary_path)
    settings.B2C_GALERI_LATEST_SNAPSHOT = str(snapshot_path)
    galeri_summary._summary_cache.update(key=None, data=None)
    galeri_summary._snapshot_cache.update(key=None, data=None)
    return summary_data, snapshot_data


def test_groups_for_merges_year_tolerance(galeri_files):
    groups = galeri_summary.groups_for("Fiat", "Egea", 2019, tolerance=1)
    years = sorted(g["year"] for g in groups)
    assert years == [2019, 2020]           # 2018 yok, 2019/2020 eşleşti


def test_price_trend_merges_weeks_across_groups(galeri_files):
    groups = b2c._galeri_groups("Fiat", "Egea", 2019)
    trend = b2c._price_trend(groups)
    by_week = {p["snapshot_date"]: p for p in trend}
    # W37: (800000*50 + 900000*30) / 80 = 837500, sample_count toplamı 80
    w37 = [p for p in trend if p["sample_count"] == 80]
    assert w37 and w37[0]["avg_price"] == 837_500


def test_regional_signal_prefers_matching_city(galeri_files):
    groups = b2c._galeri_groups("Fiat", "Egea", 2019)
    result = b2c._regional_signal(groups, "İstanbul", "")
    assert result["city"] == "İstanbul"
    assert result["delta_pct"] is not None and result["delta_pct"] > 0


def test_regional_signal_no_city_selected(galeri_files):
    groups = b2c._galeri_groups("Fiat", "Egea", 2019)
    result = b2c._regional_signal(groups, "", "")
    assert result["label"] == "Bölge belirtilmedi"


def test_color_adjustment_needs_enough_samples(galeri_files):
    groups = b2c._galeri_groups("Fiat", "Egea", 2019)
    assert b2c._color_adjustment(groups, "Beyaz") is not None
    assert b2c._color_adjustment(groups, "Turkuaz") is None       # veri yok


def test_similar_listings_matches_brand_series_year(galeri_files):
    out = b2c.similar_listings("Fiat", "Egea", 2019, price=800_000)
    assert len(out) == 2                    # 2019 ve 2020 (±1 tolerans)
    assert out[0]["url"] in {"https://example.com/1", "https://example.com/2"}


def test_locations_from_galeri_uses_snapshot(galeri_files):
    locs = b2c._locations_from_galeri()
    assert "İstanbul" in locs and "Kadıköy" in locs["İstanbul"]


def test_analyze_cached_serves_repeat_inputs_from_cache(settings):
    cache.clear()
    settings.B2C_ANALYSIS_CACHE_TTL = 60
    payload = {"brand": "Fiat", "series": "Egea", "year": 2020, "km": 1, "price": 1}
    with patch("search.services.b2c.analyze", return_value={"ok": True, "generated_at": "x", "list": [1]}) as analyze:
        first = b2c.analyze_cached(dict(payload))
        first["list"].append(2)                       # çağıranın değişikliği cache'i bozmamalı
        second = b2c.analyze_cached(dict(payload))
        b2c.analyze_cached({**payload, "km": 2})
    assert analyze.call_count == 2
    assert second["list"] == [1] and second["ok"] is True


def test_analyze_cache_can_be_disabled(settings):
    cache.clear()
    settings.B2C_ANALYSIS_CACHE_TTL = 0
    with patch("search.services.b2c.analyze", return_value={"ok": True}) as analyze:
        b2c.analyze_cached({"a": 1})
        b2c.analyze_cached({"a": 1})
    assert analyze.call_count == 2


def test_catalog_is_memoized_but_list_is_not_shared():
    a = load_arabam_vehicles()
    b = load_arabam_vehicles()
    assert a == b and a is not b
    a.clear()
    assert load_arabam_vehicles()
