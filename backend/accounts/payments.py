"""Ücretli plan aboneliği (iyzico) iş kuralları.

Akış:
1. start(): kullanıcı bilgileriyle iyzico abonelik ödeme formu başlatılır,
   PENDING kayıt açılır, form içeriği frontend'e döner.
2. complete_checkout(token): iyzico ödeme sonrası callback'e döner; sonuç
   iyzico'dan sorgulanır, ACTIVE ise plan tanımlanır, paid_until = +1 ay.
3. handle_webhook(): her ay yenileme (success) ödenen dönemi uzatır;
   başarısız ödeme UNPAID yapar. Durum her zaman iyzico'dan teyit edilir.
4. cancel(): iyzico'da iptal edilir; kullanıcı paid_until'e kadar planı kullanır.
5. expire(): paid_until (+ tolerans) geçmiş ve aktif olmayan aboneliklerde plan Basic'e döner.
"""
from __future__ import annotations

import calendar
import logging
import re
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import iyzico
from .models import PaidSubscription, PaymentEvent, Subscription

log = logging.getLogger(__name__)

PAID_PLANS = ("pro", "premium")
GRACE = timedelta(days=2)          # yenileme gecikmesine tolerans
LIVE_STATUSES = ("ACTIVE", "UNPAID", "CANCELED")


class PaymentError(Exception):
    pass


def add_month(moment: datetime) -> datetime:
    month = moment.month % 12 + 1
    year = moment.year + (moment.month // 12)
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def current(user) -> PaidSubscription | None:
    """Kullanıcının hâlâ hak sağlayan (veya bekleyen) son ücretli aboneliği."""
    return (PaidSubscription.objects.filter(user=user, status__in=LIVE_STATUSES)
            .order_by("-created_at").first())


def summary(user) -> dict:
    sub = current(user)
    return {
        "enabled": iyzico.enabled(),
        "status": sub.status if sub else None,
        "plan": sub.plan if sub else None,
        "paid_until": sub.paid_until.isoformat() if sub and sub.paid_until else None,
        "renews": bool(sub and sub.status == "ACTIVE"),
        "can_cancel": bool(sub and sub.status in ("ACTIVE", "UNPAID") and sub.reference_code),
    }


# ── Erişim süresi ───────────────────────────────────────────────────────────

def expire(sub: Subscription, now=None, save: bool = True) -> bool:
    """Ödemesi biten ücretli planı Basic'e indirir. Ücretli abonelik kaydı hiç
    olmayan (elle verilmiş) planlara dokunmaz. Değişiklik olduysa True."""
    if sub.plan not in PAID_PLANS or not sub.user_id:
        return False
    now = now or timezone.now()
    latest = PaidSubscription.objects.filter(user_id=sub.user_id).exclude(status__in=("PENDING", "FAILED")).first()
    if latest is None:
        return False
    if latest.status == "ACTIVE" and latest.plan == sub.plan:
        return False
    if latest.paid_until and latest.paid_until + GRACE > now and latest.plan == sub.plan:
        return False
    from .billing import DEFAULT_PLAN, PLANS
    sub.plan = DEFAULT_PLAN
    sub.credits = min(sub.credits, PLANS[DEFAULT_PLAN]["credits"])
    if save:
        sub.save(update_fields=["plan", "credits", "updated_at"])
        if latest.status in ("UNPAID", "CANCELED"):
            PaidSubscription.objects.filter(pk=latest.pk).update(status="EXPIRED")
    return True


def _grant(user, plan: str):
    from .billing import PLANS, _locked
    sub = _locked(user)
    if sub.plan != plan:
        sub.plan = plan
        sub.credits = PLANS[plan]["credits"]
        sub.period_start = timezone.now()
        sub.save()


# ── Başlatma ────────────────────────────────────────────────────────────────

_NAME = re.compile(r"^[^\d<>{}]{2,60}$")


def _clean_customer(user, data: dict) -> dict:
    def text(key, label, minimum=2, maximum=200):
        value = " ".join(str(data.get(key, "")).split())
        if not (minimum <= len(value) <= maximum):
            raise PaymentError(f"{label} alanını kontrol edin.")
        return value

    name, surname = text("name", "Ad", 2, 60), text("surname", "Soyad", 2, 60)
    if not (_NAME.match(name) and _NAME.match(surname)):
        raise PaymentError("Ad ve soyadı kontrol edin.")
    digits = re.sub(r"\D", "", str(data.get("phone", "")))
    if digits.startswith("90"):
        digits = digits[2:]
    digits = digits.lstrip("0")
    if len(digits) != 10 or not digits.startswith("5"):
        raise PaymentError("Geçerli bir cep telefonu girin (5xx xxx xx xx).")
    identity = re.sub(r"\D", "", str(data.get("identity_number", "")))
    if not _valid_tckn(identity):
        raise PaymentError("Geçerli bir T.C. kimlik numarası girin.")
    address, city = text("address", "Adres", 10, 300), text("city", "İl", 2, 40)
    billing_address = {"contactName": f"{name} {surname}", "city": city, "country": "Turkey", "address": address}
    return {"name": name, "surname": surname, "email": user.email, "gsmNumber": "+90" + digits,
            "identityNumber": identity, "billingAddress": billing_address, "shippingAddress": dict(billing_address)}


def _valid_tckn(value: str) -> bool:
    if len(value) != 11 or not value.isdigit() or value[0] == "0":
        return False
    d = [int(c) for c in value]
    if ((sum(d[0:9:2]) * 7 - sum(d[1:8:2])) % 10) != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


def start(user, plan: str, data: dict) -> dict:
    if not iyzico.enabled():
        raise PaymentError("Ödeme altyapısı henüz aktif değil.")
    if plan not in PAID_PLANS:
        raise PaymentError("Geçersiz plan.")
    existing = current(user)
    if existing and existing.status in ("ACTIVE", "UNPAID"):
        raise PaymentError("Zaten aktif bir aboneliğiniz var. Plan değiştirmek için önce mevcut aboneliği iptal edin.")
    customer = _clean_customer(user, data)
    conversation = uuid.uuid4().hex
    result = iyzico.init_subscription_checkout(
        plan_code=settings.IYZICO_PLAN_CODES[plan], customer=customer, conversation_id=conversation,
        callback_url=f"{settings.FRONTEND_URL}/api/b2c/payment/callback")
    token = result.get("token")
    if not token or not result.get("checkoutFormContent"):
        raise PaymentError("Ödeme formu oluşturulamadı.")
    PaidSubscription.objects.create(user=user, plan=plan, token=token, status="PENDING")
    return {"checkout_form_content": result["checkoutFormContent"], "token": token}


# ── Sonuç ve bildirimler ────────────────────────────────────────────────────

def complete_checkout(token: str) -> PaidSubscription | None:
    """iyzico callback'i. Sonuç her zaman iyzico'dan sorgulanır; gönderilen
    form verisine güvenilmez. Ödeme başarılıysa planı hemen tanımlar."""
    record = PaidSubscription.objects.filter(token=token).select_related("user").first()
    if record is None:
        return None
    if record.status != "PENDING":
        return record
    try:
        data = iyzico.retrieve_subscription_checkout(token)
    except iyzico.IyzicoError as exc:
        log.warning("iyzico checkout sonucu alınamadı: %s", exc.code or exc)
        PaidSubscription.objects.filter(pk=record.pk, status="PENDING").update(status="FAILED")
        record.status = "FAILED"
        return record
    status = str(data.get("subscriptionStatus", "")).upper()
    with transaction.atomic():
        record = PaidSubscription.objects.select_for_update().get(pk=record.pk)
        if record.status != "PENDING":
            return record
        record.reference_code = data.get("referenceCode") or None
        record.customer_reference_code = data.get("customerReferenceCode") or ""
        if status == "ACTIVE" and record.reference_code:
            record.status = "ACTIVE"
            record.paid_until = add_month(timezone.now())
            record.save()
            _grant(record.user, record.plan)
        else:
            record.status = "FAILED"
            record.save()
    return record


def handle_webhook(payload: dict, signature: str | None) -> str:
    ref = str(payload.get("subscriptionReferenceCode") or "")
    event = str(payload.get("iyziEventType") or "")
    event_id = str(payload.get("iyziReferenceCode") or "")
    if not ref or not event or not event_id:
        return "ignored"
    record = PaidSubscription.objects.filter(reference_code=ref).select_related("user").first()
    if record is None:
        return "unknown"
    signed = iyzico.webhook_signature_ok(payload, signature)
    # İmza yoksa veya doğrulanamıyorsa durum iyzico API'sinden teyit edilir.
    remote_status = None
    try:
        remote_status = str(iyzico.get_subscription(ref).get("subscriptionStatus", "")).upper() or None
    except iyzico.IyzicoError as exc:
        log.warning("iyzico abonelik durumu alınamadı: %s", exc.code or exc)
        if not signed:
            raise
    with transaction.atomic():
        _, created = PaymentEvent.objects.get_or_create(
            iyzi_reference_code=event_id,
            defaults={"event_type": event, "subscription_reference_code": ref, "payload": payload})
        if not created:
            return "duplicate"
        record = PaidSubscription.objects.select_for_update().get(pk=record.pk)
        if event == "subscription.order.success" and remote_status in (None, "ACTIVE"):
            base = max(record.paid_until or timezone.now(), timezone.now())
            record.paid_until = add_month(base)
            record.status = "ACTIVE"
            record.save()
            _grant(record.user, record.plan)
            return "renewed"
        if event == "subscription.order.failure":
            if record.status == "ACTIVE":
                record.status = "UNPAID"
                record.save(update_fields=["status", "updated_at"])
            return "unpaid"
        if remote_status in ("CANCELED", "EXPIRED") and record.status != remote_status:
            record.status = "CANCELED" if remote_status == "CANCELED" else "EXPIRED"
            record.save(update_fields=["status", "updated_at"])
    return "ok"


def cancel(user) -> PaidSubscription:
    sub = current(user)
    if not sub or sub.status not in ("ACTIVE", "UNPAID") or not sub.reference_code:
        raise PaymentError("İptal edilecek aktif bir abonelik bulunamadı.")
    iyzico.cancel_subscription(sub.reference_code)
    sub.status = "CANCELED"
    sub.canceled_at = timezone.now()
    sub.save(update_fields=["status", "canceled_at", "updated_at"])
    return sub
