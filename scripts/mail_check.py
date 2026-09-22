#!/usr/bin/env python3
"""Send one test message with the configured SMTP settings and report what failed."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.core.mail import send_mail  # noqa: E402

recipient = sys.argv[1] if len(sys.argv) > 1 else settings.EMAIL_HOST_USER
print(f"Backend : {settings.EMAIL_BACKEND}")
print(f"Sunucu  : {settings.EMAIL_HOST}:{settings.EMAIL_PORT} (TLS={settings.EMAIL_USE_TLS})")
print(f"Kullanıcı: {settings.EMAIL_HOST_USER or '(boş)'}")
print(f"Gönderen : {settings.DEFAULT_FROM_EMAIL}")
print(f"Alıcı    : {recipient or '(boş)'}\n")

if not recipient:
    sys.exit("Alıcı yok. Kullanım: .venv/bin/python scripts/mail_check.py adres@example.com")
if settings.EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    if not settings.EMAIL_HOST_PASSWORD or settings.EMAIL_HOST_PASSWORD == "BURAYA_APP_PASSWORD":
        sys.exit("B2C_SMTP_PASSWORD doldurulmamış. .env dosyasına uygulama parolasını yapıştırın.")

try:
    send_mail("Autosense SMTP testi", "Bu mesaj ulaştıysa e-posta ayarları çalışıyor.",
              settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
except Exception as error:  # noqa: BLE001 - the point is to show the provider's own message
    sys.exit(f"Gönderilemedi: {type(error).__name__}: {error}")
print("Gönderildi. Gelen kutusunu ve spam klasörünü kontrol edin.")
