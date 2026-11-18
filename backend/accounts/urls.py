from django.urls import path
from . import views
urlpatterns = [path("csrf", views.csrf), path("me", views.me), path("email/verification/request", views.resend_verification), path("account/billing", views.billing_status), path("account/plan", views.billing_plan), path("account/credits", views.billing_credits), path("payment/start", views.payment_start), path("payment/cancel", views.payment_cancel), path("payment/callback", views.payment_callback), path("payment/webhook", views.payment_webhook)]
