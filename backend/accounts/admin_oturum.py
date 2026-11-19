"""Yönetici oturumu süresi: panelde işlem yapılmazsa oturum ADMIN_SESSION_SECONDS sonra kapanır."""
from django.conf import settings


class AdminSessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if request.path.startswith("/admin/") and user is not None and user.is_authenticated and user.is_staff:
            request.session.set_expiry(getattr(settings, "ADMIN_SESSION_SECONDS", 2 * 60 * 60))
        return self.get_response(request)
