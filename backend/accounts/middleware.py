from django.utils.cache import patch_cache_control
class NoStoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/api/", "/_allauth/")):
            patch_cache_control(response, private=True, no_store=True, no_cache=True, max_age=0)
            response["Pragma"] = "no-cache"
        return response
