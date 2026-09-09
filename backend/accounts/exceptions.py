from rest_framework.views import exception_handler
from rest_framework.exceptions import NotAuthenticated, PermissionDenied

def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(exc, NotAuthenticated):
            response.data["code"] = "not_authenticated"
        elif isinstance(exc, PermissionDenied):
            response.data["code"] = "csrf_failed" if str(exc.detail).startswith("CSRF Failed") else getattr(exc.detail, "code", "permission_denied")
    return response
