from allauth.account.models import EmailAddress
from rest_framework.permissions import BasePermission
class VerifiedUser(BasePermission):
    message = "Aktif ve e-postası doğrulanmış bir hesap gereklidir."
    code = "email_verification_required"
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists())
