import json
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from allauth.account.models import EmailAddress
from allauth.account.internal.flows.email_verification import send_verification_email_to_address
from allauth.core import ratelimit
from rest_framework.decorators import api_view, permission_classes
from .permissions import VerifiedUser

@require_GET
def csrf(request):
    return JsonResponse({"csrfToken":get_token(request)})

def csrf_failure(request, reason=""):
    return JsonResponse({"code":"csrf_failed", "detail":"Güvenlik doğrulaması başarısız. Sayfayı yenileyip tekrar deneyin."}, status=403)

from .features import feature_access
from . import billing, iyzico, payments


def _billing(user):
    return {**billing.status(user), "payment": payments.summary(user)}

@api_view(["GET"])
@permission_classes([VerifiedUser])
def me(request):
    return JsonResponse({"id":request.user.pk, "email":request.user.email, "features":feature_access(request.user), "billing":_billing(request.user)})


@api_view(["GET"])
@permission_classes([VerifiedUser])
def billing_status(request):
    return JsonResponse({**_billing(request.user), **billing.catalog()})


@api_view(["POST"])
@permission_classes([VerifiedUser])
def billing_plan(request):
    try:
        billing.choose_plan(request.user, str(request.data.get("plan", "")))
        return JsonResponse({**_billing(request.user), **billing.catalog()})
    except billing.PlanRequired as exc:
        return JsonResponse({"detail":str(exc), "code":"payment_required"}, status=402)
    except ValueError as exc:
        return JsonResponse({"detail":str(exc)}, status=400)


@api_view(["POST"])
@permission_classes([VerifiedUser])
def billing_credits(request):
    try:
        amount = int(request.data.get("amount", 0))
        return JsonResponse({**billing.add_credits(request.user, amount), **billing.catalog()})
    except billing.PlanRequired as exc:
        return JsonResponse({"detail":str(exc), "code":"plan_required", "required_plan":"pro"}, status=403)
    except (TypeError, ValueError):
        return JsonResponse({"detail":"Geçersiz kredi paketi."}, status=400)

@require_POST
def resend_verification(request):
    try:
        body = json.loads(request.body)
        email = str(body.get("email", "")).strip().lower()
        validate_email(email)
    except (ValueError, ValidationError, AttributeError):
        return JsonResponse({"detail":"Geçerli bir e-posta adresi girin."}, status=400)
    limited = ratelimit.consume_or_429(request, action="b2c_resend", key=email)
    if limited:
        return JsonResponse({"detail":"Çok fazla istek. Lütfen biraz sonra tekrar deneyin."}, status=429)
    address = EmailAddress.objects.filter(email__iexact=email, verified=False, user__is_active=True).first()
    if address:
        send_verification_email_to_address(request, address, signup=True)
    return JsonResponse({"detail":"Uygun bir hesap varsa doğrulama bağlantısı gönderildi."})


# ── iyzico abonelik ödemesi ──────────────────────────────────────────────────
import logging
from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt

_log = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([VerifiedUser])
def payment_start(request):
    data = request.data if isinstance(request.data, dict) else {}
    try:
        return JsonResponse(payments.start(request.user, str(data.get("plan", "")), data))
    except payments.PaymentError as exc:
        return JsonResponse({"detail":str(exc)}, status=400)
    except iyzico.IyzicoError as exc:
        _log.warning("iyzico başlatma hatası: %s", exc.code)
        return JsonResponse({"detail":str(exc)}, status=502)


@api_view(["POST"])
@permission_classes([VerifiedUser])
def payment_cancel(request):
    try:
        payments.cancel(request.user)
    except payments.PaymentError as exc:
        return JsonResponse({"detail":str(exc)}, status=400)
    except iyzico.IyzicoError as exc:
        _log.warning("iyzico iptal hatası: %s", exc.code)
        return JsonResponse({"detail":"İptal şu an yapılamadı. Lütfen biraz sonra tekrar deneyin."}, status=502)
    return JsonResponse({**_billing(request.user), **billing.catalog()})


@csrf_exempt
@require_POST
def payment_callback(request):
    """iyzico ödeme sonrası tarayıcıyı buraya POST eder (token ile)."""
    token = str(request.POST.get("token", ""))[:128]
    record = payments.complete_checkout(token) if token else None
    ok = bool(record and record.status == "ACTIVE")
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/hesabim?odeme={'basarili' if ok else 'basarisiz'}#planlar")


@csrf_exempt
@require_POST
def payment_webhook(request):
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"detail":"bad json"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"detail":"bad json"}, status=400)
    try:
        result = payments.handle_webhook(payload, request.headers.get("X-IYZ-SIGNATURE-V3"))
    except iyzico.IyzicoError:
        return JsonResponse({"detail":"retry"}, status=503)   # iyzico tekrar dener
    return JsonResponse({"result":result})
