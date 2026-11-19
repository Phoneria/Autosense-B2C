from django.urls import include, path

from accounts.admin import site as admin_site

# _allauth/accounts/: Google gibi saglayicilarin geri donus (callback) adresleri.

urlpatterns = [path("admin/", admin_site.urls), path("_allauth/accounts/", include("allauth.urls")), path("_allauth/", include("allauth.headless.urls")), path("api/b2c/", include("accounts.urls")), path("api/", include("search.urls"))]
