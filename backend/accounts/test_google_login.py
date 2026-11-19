"""Google ile giriş (allauth headless socialaccount)."""
import pytest
from django.test import Client, override_settings
from django.urls import reverse

GOOGLE_ON = {"google": {
    "SCOPE": ["profile", "email"],
    "EMAIL_AUTHENTICATION": True,
    "APPS": [{"client_id": "test-id.apps.googleusercontent.com", "secret": "test-secret", "key": ""}],
}}


def _providers(client):
    data = client.get("/_allauth/browser/v1/config").json()["data"]
    return [p["id"] for p in data.get("socialaccount", {}).get("providers", [])]


def test_callback_url_path():
    assert reverse("google_callback") == "/_allauth/accounts/google/login/callback/"


@pytest.mark.django_db
@override_settings(SOCIALACCOUNT_PROVIDERS={"google": {"APPS": []}})
def test_google_hidden_without_credentials():
    assert "google" not in _providers(Client())


@pytest.mark.django_db
@override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE_ON)
def test_google_listed_and_redirects_to_google():
    c = Client(enforce_csrf_checks=False)
    assert "google" in _providers(c)
    r = c.post("/_allauth/browser/v1/auth/provider/redirect",
               {"provider": "google", "process": "login", "callback_url": "/login"})
    assert r.status_code == 302
    assert r["Location"].startswith("https://accounts.google.com/")
    assert "redirect_uri=" in r["Location"] and "google%2Flogin%2Fcallback" in r["Location"]
