from django.urls import path
from . import views
urlpatterns = [path("csrf", views.csrf), path("me", views.me), path("email/verification/request", views.resend_verification), path("account/billing", views.billing_status), path("account/plan", views.billing_plan), path("account/credits", views.billing_credits)]
