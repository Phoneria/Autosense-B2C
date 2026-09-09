from rest_framework.authentication import SessionAuthentication

class BrowserSessionAuthentication(SessionAuthentication):
    """Keep expired sessions (401) distinct from permission/CSRF failures (403)."""
    def authenticate_header(self, request):
        return "Session"
