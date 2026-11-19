"""Güncel piyasa (son 30 gün liste ilanları) bileşeni ve paket tahminiyle harmanlama."""
import sqlite3
from datetime import date, timedelta

import pytest

from search.pricing import central_price_estimator as central
from search.pricing import market_estimator as market

TODAY = date(2026, 10, 11)


def _make_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE liste_ilanlari (
            listing_key TEXT, snapshot_date TEXT, kaynak_link TEXT, post_url TEXT,
            model TEXT, title TEXT, year_raw TEXT, km_raw TEXT, color TEXT,
            price_raw TEXT, price INTEGER, date_raw TEXT, location TEXT,
            PRIMARY KEY (listing_key, snapshot_date))"""
    )
    conn.executemany(
        "INSERT INTO liste_ilanlari (listing_key, snapshot_date, model, year_raw, km_raw, price) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _egea_rows(n=12, model="Fiat Egea 1.3 Multijet Easy", year=2020, price=1_000_000, km="90.000"):
    return [
        (f"{model}-{i}", (TODAY - timedelta(days=i % 20)).isoformat(), model, str(year), km, price)
        for i in range(n)
    ]


@pytest.fixture
def liste_db(tmp_path, settings):
    path = tmp_path / "liste_ilanlari.db"

    def build(rows):
        _make_db(path, rows)
        settings.B2C_LISTE_DB = str(path)
        market.reload()
        return path

    yield build
    market.reload()


def _estimate(**kw):
    args = dict(category="otomobil", brand="Fiat", series="Egea", engine="1.3 Multijet",
                package="Easy", year=2020, km=90_000, damage=[])
    args.update(kw)
    return market.market_estimate(**args)


def test_market_estimate_uses_recent_comparables(liste_db):
    liste_db(_egea_rows())
    result = _estimate()
    assert result is not None
    assert result["count"] == 12
    # Aynı yıl/km -> sadece marka kalibrasyonu uygulanır.
    assert result["value"] == pytest.approx(1_000_000 * result["calibration_factor"], rel=0.01)


def test_rows_without_km_are_ignored(liste_db):
    liste_db(_egea_rows(km=None))
    assert _estimate() is None


def test_too_few_comparables_returns_none(liste_db):
    liste_db(_egea_rows(n=market.MIN_MARKET_SAMPLES - 1))
    assert _estimate() is None


def test_package_must_match_exactly(liste_db):
    liste_db(_egea_rows(model="Fiat Egea 1.3 Multijet Easy Plus"))
    assert _estimate(package="Easy") is None
    assert _estimate(package=None) is not None


def test_higher_km_lowers_market_value(liste_db):
    liste_db(_egea_rows())
    assert _estimate(km=200_000)["value"] < _estimate(km=90_000)["value"]


def test_old_snapshots_outside_window_are_dropped(liste_db):
    old = [(f"old-{i}", (TODAY - timedelta(days=60)).isoformat(), "Fiat Egea 1.3 Multijet Easy",
            "2020", "90.000", 5_000_000) for i in range(10)]
    liste_db(_egea_rows() + old)
    assert _estimate()["count"] == 12


def _fake_baseline(price):
    def fake(*args, **kwargs):
        if price is None:
            return {"found": False, "tahmini_fiyat": None, "base_count": 0}
        return {"found": True, "tahmini_fiyat": price, "base_count": 10,
                "km_factor": 1.0, "damage_factor": 1.0, "gear_factor": 1.0}
    return fake


def _central(**kw):
    args = dict(category="otomobil", brand="Fiat", series="Egea", engine="1.3 Multijet",
                package="Easy", year=2020, km=90_000, damage=[], agir_hasar=False, gear="Manuel")
    args.update(kw)
    return central.estimate_price(**args)


def test_blends_baseline_with_market(liste_db, monkeypatch):
    liste_db(_egea_rows())
    monkeypatch.setattr(central, "_predict_baseline", _fake_baseline(800_000))
    result = _central()
    assert result["estimator_engine"] == "baseline+liste"
    assert 0 < result["market_weight"] <= central.LISTE_WEIGHT_MAX
    assert result["baseline_prediction"] == 800_000
    assert 800_000 < result["tahmini_fiyat"] < result["market_prediction"]
    assert result["market_count"] == 12


def test_market_only_when_no_baseline(liste_db, monkeypatch):
    liste_db(_egea_rows())
    monkeypatch.setattr(central, "_predict_baseline", _fake_baseline(None))
    result = _central()
    assert result["found"] and result["estimator_engine"] == "liste"
    assert result["tahmini_fiyat"] == result["market_prediction"]


def test_without_liste_file_estimate_is_unchanged(tmp_path, settings, monkeypatch):
    settings.B2C_LISTE_DB = str(tmp_path / "yok.db")
    market.reload()
    monkeypatch.setattr(central, "_predict_baseline", _fake_baseline(800_000))
    result = _central()
    assert result["estimator_engine"] == "baseline"
    assert result["tahmini_fiyat"] == 800_000
    assert result["market_prediction"] is None
