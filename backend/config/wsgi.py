import logging
import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()

# Worker açılışında referans verilerini ve model listesini ısıt: ilk kullanıcı
# ~10 sn'lik soğuk başlangıcı yaşamasın. Hata olursa worker yine de açılır.
if os.getenv("B2C_WARMUP", "0") == "1":
    try:
        from search.services import b2c
        b2c.analyze({"category": "otomobil", "brand": "Fiat", "series": "Egea", "year": 2019,
                     "km": 80000, "price": 800000, "damage": []})
    except Exception:
        logging.getLogger(__name__).warning("B2C warm-up skipped", exc_info=True)
