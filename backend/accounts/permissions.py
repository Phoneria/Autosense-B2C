from allauth.account.models import EmailAddress
from rest_framework.permissions import BasePermission
class VerifiedUser(BasePermission):
    message = "Aktif ve e-postası doğrulanmış bir hesap gereklidir."
    code = "email_verification_required"
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists())


class PlanFeature(BasePermission):
    """View'in `plan_feature` özelliği kullanıcının planında yoksa 403 (plan_required)."""
    code = "plan_required"
    message = "Bu özellik mevcut planınızda yok."
    def has_permission(self, request, view):
        from . import billing
        feature = getattr(view, "plan_feature", None)
        if not feature:
            return True
        allowed = billing.plan_allows(billing.status(request.user)["plan"], feature)
        if not allowed:
            required = billing.PLANS[billing.FEATURE_MIN_PLAN.get(feature, "premium")]["name"]
            self.message = f"Bu özellik {required} planında kullanılabilir."
        return allowed
