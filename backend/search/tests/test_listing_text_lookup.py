import pytest

from search.services.listing_url_lookup import (
    ListingLookupError,
    parse_pasted_listing_text,
)


ARABAM_TEXT = """
Trink sat!
arabam.com
Fiyat
1.700.000 TL
Marka
BMW
Seri
X5
Model
30d
Yıl
2008
Kilometre
278.000 km
Vites Tipi
Otomatik
Boya, Değişen ve Tramer
Orijinal
Boyalı
Lokal Boyalı
Değişmiş
Belirtilmemiş
Boyalı
Sağ Arka Çamurluk
Sol Ön Kapı
Değişmiş
-
Tramer
"""


SAHIBINDEN_TEXT = """
sahibinden.com anasayfasına dön
Detaylı Arama
Vasıta
Otomobil
BMW
5 Serisi
520i
Comfort Plus
Karşılaştır
TEMİZ ARAÇFavorilerime EkleYazdır
İlan No 1302951902
Marka BMW
Seri 5 Serisi
Model 520i Comfort Plus
Yıl 2017
Vites Otomatik
KM 174.000
Ağır Hasar Kayıtlı Hayır
Özellikler
Boyalı veya Değişen Parça
Lokal Boyalı Parçalar
Ön Tampon
Sol Ön Çamurluk
Bagaj Kapağı
Güvenlik
"""


def test_parses_arabam_multiline_fields_and_damage():
    result = parse_pasted_listing_text(ARABAM_TEXT)

    assert result["source"] == "arabam.com"
    assert result["matched"] is True
    assert (result["brand_name"], result["series_name"], result["engine_name"]) == (
        "BMW", "X5", "30d",
    )
    assert (result["year"], result["km"], result["gear"]) == (2008, 278000, "Otomatik")
    assert result["damage_map"] == {
        "sag_arka_camurluk": "boyali",
        "sol_on_kapi": "boyali",
    }


def test_parses_sahibinden_inline_fields_package_and_damage():
    result = parse_pasted_listing_text(SAHIBINDEN_TEXT)

    assert result["source"] == "sahibinden.com"
    assert result["matched"] is True
    assert (
        result["brand_name"], result["series_name"],
        result["engine_name"], result["variant_name"],
    ) == ("BMW", "5 Serisi", "520i", "Comfort Plus")
    assert (result["year"], result["km"], result["gear"]) == (2017, 174000, "Otomatik")
    assert result["agir_hasar"] is False
    assert result["damage_map"] == {
        "on_tampon": "lokal_boyali",
        "sol_on_camurluk": "lokal_boyali",
        "arka_kaput": "lokal_boyali",
    }
    assert result["title"] == "TEMİZ ARAÇ"


def test_rejects_text_without_vehicle_fields():
    with pytest.raises(ListingLookupError, match="araç bilgisi okunamadı"):
        parse_pasted_listing_text("sahibinden.com\n" + "ilan metni " * 10)


@pytest.fixture
def authenticated_lookup_client(db):
    from accounts.models import User
    from allauth.account.models import EmailAddress
    from django.core.cache import cache
    from rest_framework.test import APIClient
    cache.clear()
    user = User.objects.create_user("parser@example.com", "Strong-parser-pass-397!")
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    client = APIClient()
    client.force_login(user)
    return client


def test_b2c_lookup_uses_shared_parser_after_login(authenticated_lookup_client):
    response = authenticated_lookup_client.post("/api/b2c/lookup-text", {"text": ARABAM_TEXT}, format="json")
    assert response.status_code == 200
    assert response.data == parse_pasted_listing_text(ARABAM_TEXT)


@pytest.mark.parametrize("text", ["", "x" * 500001, "kısa metin"], ids=["empty", "too-long", "no-vehicle"])
def test_b2c_lookup_rejects_invalid_text(authenticated_lookup_client, text):
    response = authenticated_lookup_client.post("/api/b2c/lookup-text", {"text": text}, format="json")
    assert response.status_code == 400
    assert response.data


@pytest.mark.parametrize("name,price,city,district,fuel,color,engine,variant", [
    ("bmw_standard", 1199000, "Ankara", "Etimesgut", "Dizel", "Siyah", "320d", "standart"),
    ("chrysler", 1060000, "İstanbul", "Pendik", "Dizel", "Siyah", "2-8-crd-limited", ""),
    ("volvo", 5599000, "Kocaeli", "Gebze", "Dizel", "Füme", "2-0-b5", "plus-bright"),
    ("dacia", 360000, "İstanbul", "Maltepe", "Dizel", "Lacivert", "1-5-dci", "ambiance"),
    ("bmw_m_sport", 880000, "İstanbul", "Esenyurt", "Dizel", "Siyah", "320d", "m-sport"),
])
def test_full_sahibinden_pages(name, price, city, district, fuel, color, engine, variant):
    from pathlib import Path
    text = (Path(__file__).parent / "fixtures" / "listing_text" / f"{name}.txt").read_text()
    result = parse_pasted_listing_text(text)
    assert (result["price"], result["city"], result["district"]) == (price, city, district)
    assert (result["fuel"], result["color"]) == (fuel, color)
    assert (result["engine_slug"], result["variant_slug"]) == (engine, variant)
    expected_description = text.split("\nAçıklama\n", 1)[1].split("\nÖzellikler", 1)[0].strip()
    assert result["description"] == expected_description
    assert "Güvenlik İpuçları" not in result["description"]
    assert "ABSAEBBAS" not in result["description"]


def test_description_does_not_supply_missing_summary_fields():
    text = SAHIBINDEN_TEXT.split("Özellikler")[0] + """
Açıklama
Fiyat 20.000 TL
Renk Beyaz
Yakıt Benzin
Özellikler
"""
    result = parse_pasted_listing_text(text)
    assert result["price"] is None
    assert result["fuel"] == result["color"] == ""
    assert result["description"].startswith("Fiyat 20.000 TL")


@pytest.mark.parametrize("raw,expected", [
    ("Benzin & LPG", "LPG & Benzin"), ("Benzin (Hafif Hibrit)", "Benzin"),
    ("Plug-in Hibrit", "Hibrit"), ("Elektrik", "Elektrik"),
])
def test_fuel_values(raw, expected):
    result = parse_pasted_listing_text(SAHIBINDEN_TEXT.replace("KM 174.000", f"Yakıt / Motor Tipi {raw}\nKM 174.000"))
    assert result["fuel"] == expected


JAGUAR_REVERSED_FIELDS = """
sahibinden.com anasayfasına dön
Vasıta / Otomobil / Jaguar / XE / 2.0 D / R-Sport
1.300.000 TL
Kredi Teklifi Al
Şanlıurfa / Haliliye / Paşabağı Mh.
İlan No 1332104216
Marka Jaguar
Model XE R-Sport
Seri 2.0 D
Yıl 2017
KM 180.000
Yakıt / Motor Tipi Dizel
Vites Otomatik
Renk Beyaz
Ağır Hasar Kayıtlı Evet
Açıklama
3 değişen, 1 boya mevcut.
Özellikler
Boyalı Parçalar
Sağ Arka Çamurluk
Değişen Parçalar
Motor Kaputu
Sağ Arka Kapı
Sol Ön Çamurluk
Güvenlik
"""


def test_sahibinden_reversed_model_series_uses_breadcrumb():
    result = parse_pasted_listing_text(JAGUAR_REVERSED_FIELDS)
    assert result["matched"] is True
    assert (result["series_name"], result["engine_name"], result["variant_name"]) == ("XE", "2.0 D", "")
    assert "R-Sport paketi katalogda bulunamadı" in result["warnings"][0]
    assert (result["year"], result["km"], result["price"]) == (2017, 180000, 1300000)
    assert result["agir_hasar"] is True
    assert len(result["damage_map"]) == 4


def test_breadcrumb_for_another_brand_is_not_used():
    result = parse_pasted_listing_text(JAGUAR_REVERSED_FIELDS.replace("Marka Jaguar", "Marka BMW"))
    assert result["brand_name"] == "BMW"
    assert result["series_name"] == ""


@pytest.mark.parametrize("brand,series,engine,package", [
    ("BMW", "3 Serisi", "320d", "Standart"),
    ("Dacia", "Sandero", "1.5 dCi", "Ambiance"),
    ("Jaguar", "XE", "2.0 D", "R-Sport Plus"),
])
@pytest.mark.parametrize("layout", ["normal", "reversed", "package_before_engine", "breadcrumb_only", "vertical_only"])
def test_identity_layouts_across_brands(brand, series, engine, package, layout):
    header = "sahibinden.com\n"
    if layout == "breadcrumb_only":
        identity = f"Vasıta / Otomobil / {brand} / {series} / {engine} / {package}"
    elif layout == "vertical_only":
        identity = f"Vasıta\nOtomobil\n{brand}\n{series}\n{engine}\n{package}\nFavori İlanlarım"
    elif layout == "reversed":
        identity = f"Marka {brand}\nModel {series} {package}\nSeri {engine}"
    elif layout == "package_before_engine":
        identity = f"Marka {brand}\nSeri {series}\nModel {package} {engine}"
    else:
        identity = f"Marka {brand}\nSeri {series}\nModel {engine} {package}"
    result = parse_pasted_listing_text(header + identity + "\nYıl 2017\nKM 180.000")
    assert (result["brand_name"], result["series_name"], result["engine_name"], result["variant_name"]) == (brand, series, engine, package)


def test_conflicting_paths_do_not_choose_arbitrary_engine():
    text = """sahibinden.com
Marka BMW
Vasıta / Otomobil / BMW / 3 Serisi / 320d / Standart
Vasıta / Otomobil / BMW / 3 Serisi / 318d / Standart
Yıl 2017
KM 100.000
"""
    result = parse_pasted_listing_text(text)
    assert result["series_name"] == "3 Serisi"
    assert result["engine_slug"] == result["variant_slug"] == ""
    assert any("belirsiz" in warning for warning in result["warnings"])


def test_repeated_photo_paths_do_not_outvote_conflicting_identity():
    first = "Vasıta / Otomobil / BMW / 3 Serisi / 320d / Standart\n"
    second = "Vasıta / Otomobil / BMW / 3 Serisi / 318d / Standart\n"
    result = parse_pasted_listing_text("sahibinden.com\nMarka BMW\n" + first * 20 + second)
    assert result["engine_slug"] == ""


def test_conflicting_package_names_of_different_lengths_stay_unselected():
    text = """sahibinden.com
Marka BMW
Vasıta / Otomobil / BMW / 3 Serisi / 320d / Standart
Vasıta / Otomobil / BMW / 3 Serisi / 320d / M Sport
"""
    result = parse_pasted_listing_text(text)
    assert result["engine_name"] == "320d"
    assert result["variant_slug"] == ""


def test_seller_prose_cannot_override_catalog_identity():
    text = SAHIBINDEN_TEXT + "\nAçıklama\nVasıta / Otomobil / BMW / 3 Serisi / 320d / Standart"
    result = parse_pasted_listing_text(text)
    assert result["series_name"] == "5 Serisi"


def test_full_arabam_page_reads_location_and_description():
    """arabam.com ilan sayfası: konum etiketsiz tek satırda ("Fevzi Çakmak Mh.
    Esenler, İstanbul") ve "Açıklama" başlığı önce sekme menüsünde geçiyor."""
    from pathlib import Path
    text = (Path(__file__).parent / "fixtures" / "listing_text" / "arabam_egea.txt").read_text()
    result = parse_pasted_listing_text(text)

    assert result["source"] == "arabam.com"
    assert (result["city"], result["district"]) == ("İstanbul", "Esenler")
    assert result["description"].startswith("ARACIMDA DEĞİŞEN YOK")
    assert result["description"].endswith("PAZARLIK USULÜNCE OLUR.")
    assert "Boya, Değişen ve Tramer" not in result["description"]
    assert (result["year"], result["km"], result["price"]) == (2024, 115000, 950000)
    assert (result["fuel"], result["color"], result["gear"]) == ("Dizel", "Beyaz", "Manuel")
    assert result["damage_map"]["sag_arka_camurluk"] == "lokal_boyali"
    assert result["damage_map"]["arka_kaput"] == "lokal_boyali"
    assert result["agir_hasar"] is False


from pathlib import Path

SAHIBINDEN_PATH = Path(__file__).parent / "fixtures/listing_text/sahibinden_superb.txt"


def test_sahibinden_glued_labels_are_parsed():
    """sahibinden.com etiket ve değeri aynı satırda boşluksuz veriyor
    ("Yıl2011", "KM270.000", "RenkBeyaz") -- bu alanlar da dolmalı."""
    text = SAHIBINDEN_PATH.read_text(encoding="utf-8")
    result = parse_pasted_listing_text(text)
    assert result["brand_name"] == "Skoda" and result["series_name"].lower() == "superb"
    assert result["year"] == 2011
    assert result["km"] == 270000
    assert result["price"] == 1050000
    assert result["color"] == "Beyaz"
    assert result["fuel"] == "LPG & Benzin"
    assert result["gear"] == "Manuel"
    assert result["agir_hasar"] is False
    assert (result["city"], result["district"]) == ("Van", "İpekyolu")
    assert result["damage_map"] == {"sol_arka_kapi": "lokal_boyali", "sol_arka_camurluk": "lokal_boyali"}


def test_glued_label_does_not_swallow_ordinary_words():
    """"Markalı araç" gibi bir satır "Marka" etiketi sanılmamalı."""
    from search.services.listing_url_lookup import _find_field_values
    values = _find_field_values(["Markalı araç arıyorsanız", "Yıl2018", "Renkbeyaz metalik"])
    assert values["marka"] == ""
    assert values["yil"] == "2018"
    assert values["renk"] == ""
