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

@api_view(["GET"])
@permission_classes([VerifiedUser])
def me(request):
    return JsonResponse({"id":request.user.pk, "email":request.user.email, "features":feature_access(request.user)})

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
