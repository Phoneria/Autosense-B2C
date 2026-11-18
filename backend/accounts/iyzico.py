"""iyzico API istemcisi (yalnızca standart kütüphane).

Kimlik doğrulama IYZWSv2: HMAC-SHA256(randomKey + uriPath + body, secretKey).
Anahtarlar yalnızca ortam değişkenlerinden okunur; koda veya loglara yazılmaz.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request

from django.conf import settings


class IyzicoError(Exception):
    def __init__(self, message: str, code: str | None = None, payload: dict | None = None):
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


def enabled() -> bool:
    return bool(settings.IYZICO_API_KEY and settings.IYZICO_SECRET_KEY
                and settings.IYZICO_PLAN_CODES.get("pro") and settings.IYZICO_PLAN_CODES.get("premium"))


def _auth_header(path: str, body: str, rnd: str) -> str:
    signature = hmac.new(settings.IYZICO_SECRET_KEY.encode(), (rnd + path + body).encode(), hashlib.sha256).hexdigest()
    raw = f"apiKey:{settings.IYZICO_API_KEY}&randomKey:{rnd}&signature:{signature}"
    return "IYZWSv2 " + base64.b64encode(raw.encode()).decode()


def request(method: str, path: str, payload: dict | None = None, timeout: int = 20) -> dict:
    body = "" if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    rnd = secrets.token_hex(8)
    req = urllib.request.Request(
        settings.IYZICO_BASE_URL.rstrip("/") + path,
        data=body.encode() if payload is not None else None,
        method=method,
        headers={"Authorization": _auth_header(path, body, rnd), "x-iyzi-rnd": rnd,
                 "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode() or "{}")
        except ValueError:
            raise IyzicoError(f"iyzico HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise IyzicoError("Ödeme sağlayıcısına ulaşılamadı. Lütfen biraz sonra tekrar deneyin.") from exc
    if data.get("status") != "success":
        raise IyzicoError(data.get("errorMessage") or "Ödeme işlemi başlatılamadı.", data.get("errorCode"), data)
    return data


# ── Abonelik uçları ─────────────────────────────────────────────────────────

def init_subscription_checkout(*, plan_code: str, customer: dict, callback_url: str, conversation_id: str) -> dict:
    return request("POST", "/v2/subscription/checkoutform/initialize", {
        "locale": "tr",
        "conversationId": conversation_id,
        "callbackUrl": callback_url,
        "pricingPlanReferenceCode": plan_code,
        "subscriptionInitialStatus": "ACTIVE",
        "customer": customer,
    })


def retrieve_subscription_checkout(token: str) -> dict:
    return request("GET", f"/v2/subscription/checkoutform/{token}").get("data") or {}


def get_subscription(reference_code: str) -> dict:
    data = request("GET", f"/v2/subscription/subscriptions/{reference_code}").get("data") or {}
    # Yanıt bazen tek kayıt, bazen {"items": [...]} biçiminde döner.
    if isinstance(data.get("items"), list) and data["items"]:
        return data["items"][0]
    return data


def cancel_subscription(reference_code: str) -> dict:
    return request("POST", f"/v2/subscription/subscriptions/{reference_code}/cancel", {})


def webhook_signature_ok(payload: dict, header_value: str | None) -> bool:
    """X-IYZ-SIGNATURE-V3 (abonelik biçimi). Merchant ID tanımlı değilse doğrulanamaz."""
    if not (settings.IYZICO_MERCHANT_ID and header_value):
        return False
    message = (settings.IYZICO_MERCHANT_ID + settings.IYZICO_SECRET_KEY + str(payload.get("iyziEventType", ""))
               + str(payload.get("subscriptionReferenceCode", "")) + str(payload.get("orderReferenceCode", ""))
               + str(payload.get("customerReferenceCode", "")))
    expected = hmac.new(settings.IYZICO_SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), header_value.strip().lower())
