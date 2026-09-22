#!/usr/bin/env python3
"""Yük testi için doğrulanmış kullanıcılar + hazır oturum çerezleri üretir.

Login uç noktası IP başına 20/dk ile sınırlı olduğundan (bilerek), yük testi
oturumları doğrudan oluşturur. SADECE test/staging veritabanında çalıştırın.

  B2C_ACCOUNT_DB=/tmp/lt.sqlite3 B2C_DEBUG=true python scripts/loadtest/seed_users.py 1000
  # Sunucuda: docker compose exec backend python /app/loadtest/seed_users.py ... (bkz. README)
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from allauth.account.models import EmailAddress  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY  # noqa: E402
from django.contrib.sessions.backends.db import SessionStore  # noqa: E402

from accounts.models import User  # noqa: E402


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("sessions.json")
    sessions = []
    for i in range(count):
        email = f"loadtest{i}@example.com"
        user = User.objects.filter(email=email).first() or User.objects.create_user(email, "Long-strong-test-472!")
        EmailAddress.objects.update_or_create(user=user, email=email, defaults={"verified": True, "primary": True})
        store = SessionStore()
        store[SESSION_KEY] = str(user.pk)
        store[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
        store[HASH_SESSION_KEY] = user.get_session_auth_hash()
        store.save()
        sessions.append(store.session_key)
    out.write_text(json.dumps(sessions))
    print(f"{count} kullanıcı hazır -> {out}")


if __name__ == "__main__":
    main()
