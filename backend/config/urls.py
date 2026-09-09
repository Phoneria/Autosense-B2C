from django.urls import include, path
urlpatterns = [path("_allauth/", include("allauth.headless.urls")), path("api/b2c/", include("accounts.urls")), path("api/", include("search.urls"))]
