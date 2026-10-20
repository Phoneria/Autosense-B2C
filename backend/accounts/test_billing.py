from datetime import timedelta
from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from accounts import billing
from accounts.models import Subscription, User

PAYLOAD = {"brand": "Fiat", "series": "Egea", "engine": "1.3 Multijet", "package": "Easy",
           "year": 2023, "km": 100000, "price": 1200000}


@pytest.fixture
def user(db):
    cache.clear()
    u = User.objects.create_user("billing@example.com", "Long-strong-test-472!")
    EmailAddress.objects.create(user=u, email=u.email, verified=True, primary=True)
    return u


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


def test_new_user_starts_on_basic_with_three_credits(client):
    data = client.get("/api/b2c/account/billing").json()
    assert data["plan"] == "basic" and data["credits"] == 3 and data["total_credits"] == 3
    assert {p["id"] for p in data["plans"]} == {"basic", "pro", "premium"}
    assert client.get("/api/b2c/me").json()["billing"]["plan_name"] == "Basic"


def test_analysis_spends_credit_and_blocks_when_empty(client, user):
    with patch("search.views.b2c.analyze", return_value={"ok": True}):
        for left in (2, 1, 0):
            r = client.post("/api/b2c/analyze", PAYLOAD, content_type="application/json")
            assert r.status_code == 200 and r.json()["billing"]["credits"] == left
        r = client.post("/api/b2c/analyze", PAYLOAD, content_type="application/json")
    assert r.status_code == 402 and r.json()["code"] == "no_credits"


def test_failed_analysis_refunds_credit(client):
    with patch("search.views.b2c.analyze", side_effect=ValueError):
        assert client.post("/api/b2c/analyze", PAYLOAD, content_type="application/json").status_code == 400
    assert client.get("/api/b2c/account/billing").json()["credits"] == 3


def test_plan_credits_reset_daily_at_istanbul_midnight(client, user):
    billing.choose_plan(user, "pro")
    for _ in range(15):
        billing.consume(user)
    with pytest.raises(billing.NoCredits):
        billing.consume(user)
    sub = Subscription.objects.get(user=user)
    start = billing._day_start(sub.period_start)
    with patch("accounts.billing.timezone.now", return_value=start + timedelta(hours=23, minutes=59)):
        assert billing.status(user)["credits"] == 0
    with patch("accounts.billing.timezone.now", return_value=start + timedelta(days=1, seconds=5)):
        data = billing.status(user)
    assert data["credits"] == 15 and data["extra_credits"] == 0
    assert data["next_reset_at"] == (start + timedelta(days=2)).isoformat()


def test_premium_is_unlimited(client, user):
    billing.choose_plan(user, "premium")
    for _ in range(60):
        assert billing.consume(user)["_source"] == "unlimited"
    with patch("search.views.b2c.analyze", return_value={"ok": True}):
        assert client.post("/api/b2c/analyze", PAYLOAD, content_type="application/json").status_code == 200
    data = client.get("/api/b2c/account/billing").json()
    assert data["unlimited"] is True and data["credits"] == 50
    prices = {p["id"]: p["price_label"] for p in data["plans"]}
    assert prices == {"basic": "Ücretsiz", "pro": "₺499 / ay", "premium": "₺2.999 / ay"}


def test_extra_credits_removed(client, user):
    billing.choose_plan(user, "premium")
    r = client.post("/api/b2c/account/credits", {"amount": 10}, content_type="application/json")
    assert r.json()["code"] == "plan_required"
    data = client.get("/api/b2c/account/billing").json()
    assert data["credit_packs"] == [] and "extra_credits" not in data["plan_features"]


def test_choose_plan_is_approved_immediately(client):
    r = client.post("/api/b2c/account/plan", {"plan": "pro"}, content_type="application/json")
    assert r.status_code == 200 and r.json()["plan_name"] == "Pro" and r.json()["credits"] == 15
    assert client.post("/api/b2c/account/plan", {"plan": "gold"}, content_type="application/json").status_code == 400


def test_scenario_and_cost_do_not_spend_credits(client, user):
    with patch("search.views.b2c.scenario", return_value={"ok": True}):
        assert client.post("/api/b2c/scenario", PAYLOAD, content_type="application/json").status_code == 403
    billing.choose_plan(user, "pro")
    with patch("search.views.b2c.scenario", return_value={"ok": True}):
        assert client.post("/api/b2c/scenario", PAYLOAD, content_type="application/json").status_code == 200
    r = client.post("/api/b2c/cost", {"engine": "1.3 Multijet", "year": 2023, "annual_km": 12000,
                                       "vehicle_value": 1000000, "kasko_tl": 30000}, content_type="application/json")
    assert r.status_code == 200 and r.json()["total_yearly_tl"] > 0
    assert client.get("/api/b2c/account/billing").json()["credits"] == 15


def test_regional_deals_requires_premium(client, user):
    fake = {"snapshot_date": "2026-09-05", "thresholds": {}, "cities": [{"city": "İstanbul", "listings": 10}], "deals": []}
    with patch("search.views.regional.overview", return_value=fake):
        r = client.get("/api/b2c/regional-deals")
        assert r.status_code == 403 and r.json()["code"] == "plan_required"
        billing.choose_plan(user, "premium")
        assert client.get("/api/b2c/regional-deals").json()["cities"][0]["city"] == "İstanbul"


def test_vehicle_guide_hides_charts_for_non_premium(client, user):
    fake_model = {"key": "fiat-egea", "name": "Fiat Egea", "category": "otomobil", "median_price": 900000,
                  "weekly": {"stock": [1]}, "trait_engines": []}
    fake = {"snapshot_date": "2026-09-05", "first_date": "2026-06-15", "snapshot_count": 59, "window_days": 30,
            "weeks": ["2026-08-31"], "home": {}, "models": {"fiat-egea": {**fake_model, "active": 1, "removed_30d": 1,
            "median_days_on_market": 10, "price_change_4w_pct": 0, "turnover_pct": 1}}}
    with patch("search.services.guide.get", return_value=fake):
        assert client.get("/api/b2c/guide").status_code == 403
        billing.choose_plan(user, "pro")
        pro_model = client.get("/api/b2c/guide/model?key=fiat-egea").json()
        assert "weekly" not in pro_model and pro_model["lock"]["required_plan"] == "premium"
        assert client.get("/api/b2c/guide").json()["models"][0]["key"] == "fiat-egea"
        basic = client.get("/api/b2c/guide/model?key=fiat-egea").json()
        assert "weekly" not in basic and basic["premium"] is False
        assert client.get("/api/b2c/guide/compare?keys=fiat-egea").status_code == 403
        billing.choose_plan(user, "premium")
        assert "weekly" in client.get("/api/b2c/guide/model?key=fiat-egea").json()
        assert client.get("/api/b2c/guide/compare?keys=fiat-egea").status_code == 200
        assert client.get("/api/b2c/guide/model?key=yok").status_code == 404


def test_plan_feature_matrix(client, user):
    features = client.get("/api/b2c/account/billing").json()["plan_features"]
    assert features == ["analysis"]
    billing.choose_plan(user, "pro")
    pro = billing.status(user)["plan_features"]
    assert {"guide", "regional", "depreciation", "estimate_details"} <= set(pro)
    assert {"similar_listings", "regional_listings", "guide_model_detail"}.isdisjoint(pro)
    with patch("search.views.regional.overview", return_value={"cities": [], "deals": []}):
        assert client.get("/api/b2c/regional-deals").status_code == 200


def test_analysis_locks_sections_by_plan(client, user):
    result = {"similar_listings": [{"title": "x", "price": 1}], "depreciation": {"available": True, "one_year_value": 5},
              "evidence": {"strength": "strong", "unique_comparables": 42, "reference_listings": 7},
              "data_sources": {"gallery_matches": 9}}
    with patch("search.views.b2c.analyze", return_value=dict(result)):
        basic = client.post("/api/b2c/analyze", PAYLOAD, content_type="application/json").json()
    assert basic["similar_listings"] == [] and basic["locks"]["similar_listings"]["count"] == 1
    assert basic["locks"]["similar_listings"]["required_plan"] == "premium"
    assert basic["depreciation"]["one_year_value"] is None
    assert basic["locks"]["depreciation"]["required_plan"] == "pro"
    assert basic["evidence"] == {"strength": "strong", "locked": True} and basic["data_sources"] is None

    billing.choose_plan(user, "pro")
    with patch("search.views.b2c.analyze", return_value=dict(result)):
        pro = client.post("/api/b2c/analyze", PAYLOAD, content_type="application/json").json()
    assert pro["depreciation"]["one_year_value"] == 5 and pro["evidence"]["reference_listings"] == 7
    assert pro["similar_listings"] == [] and "similar_listings" in pro["locks"]

    billing.choose_plan(user, "premium")
    with patch("search.views.b2c.analyze", return_value=dict(result)):
        premium = client.post("/api/b2c/analyze", PAYLOAD, content_type="application/json").json()
    assert premium["similar_listings"] and premium["locks"] == {}


def test_regional_listings_locked_for_pro(client, user):
    overview = {"snapshot_date": "2026-09-05", "thresholds": {}, "cities": [{"city": "İstanbul"}],
                "deals": [{"city": "İstanbul", "model": "Fiat Egea", "top_listings": [{"title": "x", "price": 1}]}]}
    assert client.get("/api/b2c/regional-deals").status_code == 403           # basic
    billing.choose_plan(user, "pro")
    with patch("search.views.regional.overview", return_value=overview):
        pro = client.get("/api/b2c/regional-deals").json()
        assert pro["deals"][0]["top_listings"] == [] and pro["listings_lock"]["required_plan"] == "premium"
        billing.choose_plan(user, "premium")
        premium = client.get("/api/b2c/regional-deals").json()
        assert premium["deals"][0]["top_listings"] and "listings_lock" not in premium


def test_status_never_writes(client, user):
    """/me ve izin kontrolleri her istekte çalışıyor; yazarlarsa SQLite
    eşzamanlı isteklerde kilitleniyordu."""
    assert client.get("/api/b2c/me").json()["billing"]["credits"] == 3
    assert client.get("/api/b2c/account/billing").json()["plan"] == "basic"
    assert Subscription.objects.filter(user=user).count() == 0
    with patch("search.views.b2c.analyze", return_value={"ok": True}):
        client.post("/api/b2c/analyze", PAYLOAD, content_type="application/json")
    assert Subscription.objects.get(user=user).credits == 2
    assert client.get("/api/b2c/me").json()["billing"]["credits"] == 2
