import hashlib
import hmac
from datetime import timedelta
from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone

from accounts import billing, iyzico, payments
from accounts.models import PaidSubscription, PaymentEvent, Subscription, User

KEYS = dict(IYZICO_API_KEY="sandbox-key", IYZICO_SECRET_KEY="sandbox-secret", IYZICO_MERCHANT_ID="",
            IYZICO_BASE_URL="https://sandbox-api.iyzipay.com",
            IYZICO_PLAN_CODES={"pro": "PLAN-PRO", "premium": "PLAN-PREMIUM"})
FORM = {"plan": "pro", "name": "Ayşe", "surname": "Yılmaz", "phone": "0532 123 45 67",
        "identity_number": "10000000146", "address": "Atatürk Cad. No: 1 Daire 2, Çankaya", "city": "Ankara"}


@pytest.fixture
def user(db):
    cache.clear()
    u = User.objects.create_user("pay@example.com", "Long-strong-test-472!")
    EmailAddress.objects.create(user=u, email=u.email, verified=True, primary=True)
    return u


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


def _start(client):
    with patch("accounts.iyzico.init_subscription_checkout",
               return_value={"token": "tok-1", "checkoutFormContent": "<script>iyzi</script>"}) as init:
        r = client.post("/api/b2c/payment/start", FORM, content_type="application/json")
    return r, init


def _activate(client):
    _start(client)
    with patch("accounts.iyzico.retrieve_subscription_checkout",
               return_value={"subscriptionStatus": "ACTIVE", "referenceCode": "SUB-1", "customerReferenceCode": "CUS-1"}):
        return client.post("/api/b2c/payment/callback", {"token": "tok-1"})


def test_auth_header_matches_documented_iyzwsv2_format():
    with override_settings(**KEYS):
        header = iyzico._auth_header("/v2/x", '{"a":1}', "rnd123")
    import base64
    raw = base64.b64decode(header.split(" ", 1)[1]).decode()
    sig = hmac.new(b"sandbox-secret", b'rnd123/v2/x{"a":1}', hashlib.sha256).hexdigest()
    assert header.startswith("IYZWSv2 ") and raw == f"apiKey:sandbox-key&randomKey:rnd123&signature:{sig}"


def test_payment_disabled_without_keys(client):
    assert client.get("/api/b2c/me").json()["billing"]["payment"]["enabled"] is False
    r = client.post("/api/b2c/payment/start", FORM, content_type="application/json")
    assert r.status_code == 400


@override_settings(**KEYS)
def test_paid_plan_cannot_be_chosen_without_payment(client):
    r = client.post("/api/b2c/account/plan", {"plan": "premium"}, content_type="application/json")
    assert r.status_code == 402 and r.json()["code"] == "payment_required"
    assert Subscription.objects.filter(plan="premium").count() == 0


@override_settings(**KEYS)
def test_start_validates_customer_and_sends_plan_code(client):
    bad = dict(FORM, identity_number="12345678901")
    assert client.post("/api/b2c/payment/start", bad, content_type="application/json").status_code == 400
    r, init = _start(client)
    assert r.status_code == 200 and r.json()["checkout_form_content"]
    kwargs = init.call_args.kwargs
    assert kwargs["plan_code"] == "PLAN-PRO" and kwargs["customer"]["gsmNumber"] == "+905321234567"
    assert kwargs["callback_url"].endswith("/api/b2c/payment/callback")
    assert PaidSubscription.objects.get().status == "PENDING"


@override_settings(**KEYS)
def test_successful_callback_grants_plan_for_one_month(client, user):
    r = _activate(client)
    assert r.status_code == 302 and "odeme=basarili" in r["Location"]
    rec = PaidSubscription.objects.get()
    assert rec.status == "ACTIVE" and rec.reference_code == "SUB-1"
    assert 27 <= (rec.paid_until - timezone.now()).days <= 31
    data = client.get("/api/b2c/account/billing").json()
    assert data["plan"] == "pro" and data["payment"]["renews"] and data["payment"]["can_cancel"]


@override_settings(**KEYS)
def test_failed_callback_does_not_grant(client):
    _start(client)
    with patch("accounts.iyzico.retrieve_subscription_checkout", side_effect=iyzico.IyzicoError("declined")):
        r = client.post("/api/b2c/payment/callback", {"token": "tok-1"})
    assert "odeme=basarisiz" in r["Location"]
    assert client.get("/api/b2c/account/billing").json()["plan"] == "basic"
    assert client.post("/api/b2c/payment/callback", {"token": "nope"}).status_code == 302


@override_settings(**KEYS)
def test_renewal_webhook_extends_and_is_idempotent(client):
    _activate(client)
    before = PaidSubscription.objects.get().paid_until
    body = {"iyziEventType": "subscription.order.success", "subscriptionReferenceCode": "SUB-1",
            "orderReferenceCode": "ORD-2", "customerReferenceCode": "CUS-1", "iyziReferenceCode": "EVT-2"}
    with patch("accounts.iyzico.get_subscription", return_value={"subscriptionStatus": "ACTIVE"}):
        assert client.post("/api/b2c/payment/webhook", body, content_type="application/json").json()["result"] == "renewed"
        assert client.post("/api/b2c/payment/webhook", body, content_type="application/json").json()["result"] == "duplicate"
    assert PaidSubscription.objects.get().paid_until > before + timedelta(days=27)
    assert PaymentEvent.objects.count() == 1


@override_settings(**KEYS)
def test_unverified_webhook_is_retried_when_api_unreachable(client):
    _activate(client)
    body = {"iyziEventType": "subscription.order.success", "subscriptionReferenceCode": "SUB-1",
            "orderReferenceCode": "ORD-2", "customerReferenceCode": "CUS-1", "iyziReferenceCode": "EVT-3"}
    with patch("accounts.iyzico.get_subscription", side_effect=iyzico.IyzicoError("down")):
        assert client.post("/api/b2c/payment/webhook", body, content_type="application/json").status_code == 503
    assert PaymentEvent.objects.count() == 0


@override_settings(**KEYS)
def test_cancel_keeps_plan_until_paid_period_ends(client, user):
    _activate(client)
    with patch("accounts.iyzico.cancel_subscription", return_value={"status": "success"}):
        data = client.post("/api/b2c/payment/cancel").json()
    assert data["plan"] == "pro" and data["payment"]["status"] == "CANCELED" and not data["payment"]["renews"]
    PaidSubscription.objects.update(paid_until=timezone.now() - timedelta(days=3))
    assert client.get("/api/b2c/account/billing").json()["plan"] == "basic"
    with patch("search.views.b2c.analyze", return_value={"ok": True}):
        client.post("/api/b2c/analyze", {"brand": "Fiat", "series": "Egea", "engine": "1.3 Multijet", "package": "Easy",
                                          "year": 2023, "km": 100000, "price": 1200000}, content_type="application/json")
    assert Subscription.objects.get(user=user).plan == "basic"
    assert PaidSubscription.objects.get().status == "EXPIRED"


@override_settings(**KEYS)
def test_manually_granted_plan_is_untouched(user):
    Subscription.objects.create(user=user, plan="premium", credits=50, period_start=timezone.now())
    assert billing.status(user)["plan"] == "premium"


@override_settings(**dict(KEYS, IYZICO_MERCHANT_ID="M1"))
def test_webhook_signature_formula():
    p = {"iyziEventType": "subscription.order.success", "subscriptionReferenceCode": "S",
         "orderReferenceCode": "O", "customerReferenceCode": "C"}
    sig = hmac.new(b"sandbox-secret", b"M1sandbox-secretsubscription.order.successSOC", hashlib.sha256).hexdigest()
    assert iyzico.webhook_signature_ok(p, sig) and not iyzico.webhook_signature_ok(p, "x" * 64)


def test_tckn_validation():
    assert payments._valid_tckn("10000000146") and not payments._valid_tckn("12345678901")
