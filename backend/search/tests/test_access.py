from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import Client

from accounts.models import User

ENDPOINTS = [
    ("get", "/api/arabam-vehicles"), ("get", "/api/b2c/vehicles"),
    ("get", "/api/b2c/locations"), ("post", "/api/b2c/vehicle-defaults"), ("get", "/api/b2c/regional-deals"),
    ("post", "/api/b2c/lookup-text"), ("post", "/api/b2c/analyze"),
]
PAYLOAD = {"brand":"Fiat", "series":"Egea", "engine":"1.3 Multijet", "package":"Easy", "year":2023, "km":100000, "price":1200000}


@pytest.fixture
def user(db):
    cache.clear()
    u = User.objects.create_user("analysis@example.com", "Long-strong-test-472!")
    EmailAddress.objects.create(user=u, email=u.email, verified=True, primary=True)
    return u


@pytest.mark.django_db
@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_anonymous_cannot_access_any_business_endpoint(method, path):
    c = Client()
    response = getattr(c, method)(path, {}, content_type="application/json")
    assert response.status_code == 401


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_unverified_cannot_access_any_business_endpoint(user, method, path):
    EmailAddress.objects.filter(user=user).update(verified=False)
    c = Client()
    c.force_login(user)
    response = getattr(c, method)(path, {}, content_type="application/json")
    assert response.status_code == 403


def test_cookie_session_requires_csrf_for_analysis(user):
    c = Client(enforce_csrf_checks=True)
    c.force_login(user)
    assert c.post("/api/b2c/analyze", PAYLOAD, content_type="application/json").status_code == 403
    csrf = c.get("/api/b2c/csrf").json()["csrfToken"]
    with patch("search.views.b2c.analyze", return_value={"ok":True}) as analyze:
        r = c.post("/api/b2c/analyze", PAYLOAD, content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
    assert r.status_code == 200
    assert analyze.call_args.args[0]["brand"] == "Fiat"


@pytest.mark.parametrize("change", [{"km":"NaN"}, {"price":"Infinity"}, {"damage":[None]}, {"damage":[{"parca":"invented", "durum":"Boyalı"}]}, {"year":12}, {"description":"x"*50001}])
def test_malformed_analysis_rejected_before_engine(user, change):
    c = Client()
    c.force_login(user)
    with patch("search.views.b2c.analyze") as analyze:
        r = c.post("/api/b2c/analyze", {**PAYLOAD, **change}, content_type="application/json")
    assert r.status_code == 400
    analyze.assert_not_called()


def test_frontend_damage_labels_and_optional_location_are_preserved(user):
    c = Client()
    c.force_login(user)
    with patch("search.views.b2c.analyze", return_value={"ok":True}) as analyze:
        r = c.post("/api/b2c/analyze", {**PAYLOAD, "damage":[{"parca":"Kaput", "durum":"Değişmiş"}], "plan":"premium"}, content_type="application/json")
    assert r.status_code == 200
    assert "city" not in analyze.call_args.args[0]
    assert "plan" not in analyze.call_args.args[0]


def test_analysis_rate_limit_is_enforced(user):
    from accounts import billing
    billing.choose_plan(user, "premium")
    c = Client()
    c.force_login(user)
    with patch("search.views.b2c.analyze", return_value={}):
        results = [c.post("/api/b2c/analyze", PAYLOAD, content_type="application/json").status_code for _ in range(21)]
    assert results == [200]*20+[429]


def test_missing_baseline_returns_recoverable_error(user):
    c = Client()
    c.force_login(user)
    with patch("search.views.b2c.analyze", side_effect=FileNotFoundError("private path")):
        r = c.post("/api/b2c/analyze", PAYLOAD, content_type="application/json")
    assert r.status_code == 503
    assert "private path" not in str(r.content)
