"""Seçilen paketin referansı zayıfsa analiz boş dönmemeli."""
import pytest

from search.services import b2c


@pytest.mark.parametrize("package,expected_trim", [("Elegance", "engine_median"), (None, "engine_median")])
def test_weak_package_reference_falls_back_to_engine_median(package, expected_trim):
    # Skoda SuperB 1.4 TSI Elegance referansı tek ilana dayanıyor (MIN_PAKET_SAMPLES altı).
    estimate = b2c._estimate_vehicle(
        category="otomobil", brand="Skoda", series="SuperB", engine="1.4 TSI",
        package=package, year=2011, km=270000, damage=[], agir_hasar=False, gear="Manuel",
    )
    assert estimate["found"] and estimate["tahmini_fiyat"] > 0
    assert estimate["package_fallback"]["count"] >= 1
    assert estimate["confidence_pct"] <= 45
    evidence = b2c._evidence(estimate, brand="Skoda", series="SuperB", year=2011, package=package)
    assert evidence["trim_match"] == expected_trim
    if package:
        assert package in estimate["fallback_reason"]


def test_rich_package_reference_still_wins():
    estimate = b2c._estimate_vehicle(
        category="otomobil", brand="Fiat", series="Egea", engine="1.3 Multijet",
        package="Easy", year=2023, km=100000, damage=[], agir_hasar=False, gear="Manuel",
    )
    assert estimate["found"] and not estimate.get("package_fallback")
    assert estimate["confidence_pct"] >= 55
