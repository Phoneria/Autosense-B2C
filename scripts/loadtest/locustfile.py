"""AutoSense B2C yük testi (Locust).

  pip install locust
  python scripts/loadtest/seed_users.py 1000            # test DB'sinde!
  locust -f scripts/loadtest/locustfile.py --host https://TEST_DOMAIN \
         -u 1000 -r 25 --run-time 5m --headless

Her sanal kullanıcı hazır bir oturum çerezi ile başlar, sonra gerçekçi bir
karışım çalıştırır: analiz (ağır), katalog, konum, profil. 402 (kredi bitti)
ve 429 (throttle) uygulamanın beklenen yanıtlarıdır, hata sayılmaz.
"""
import json
import random
from pathlib import Path
from urllib.parse import urlparse

from locust import HttpUser, between, task

SESSIONS = json.loads(Path(__file__).with_name("sessions.json").read_text())
POPULAR = {"Fiat", "Renault", "Volkswagen", "Toyota", "Ford", "Opel", "Hyundai", "Honda", "Peugeot", "BMW"}
CARS: list = []   # (marka, seri, motor) -- ilk sanal kullanıcı katalogdan doldurur
_next = 0


class Buyer(HttpUser):
    wait_time = between(5, 15)

    def on_start(self):
        global _next
        self.session_key = SESSIONS[_next % len(SESSIONS)]
        _next += 1
        host = urlparse(self.host).hostname
        self.client.cookies.set("b2c_sessionid", self.session_key, domain=host, path="/")
        if not CARS:
            catalog = self.client.get("/api/b2c/vehicles", name="vehicles")
            if catalog.ok:
                for brand in catalog.json():
                    if brand["name"] in POPULAR:
                        for ser in brand["series"]:
                            for eng in ser["engines"][:2]:
                                CARS.append((brand["name"], ser["name"], eng["name"]))
        r = self.client.get("/api/b2c/csrf", name="csrf")
        self.csrf = r.json().get("csrfToken", "") if r.ok else ""

    def _post(self, path, body, name):
        with self.client.post(path, json=body, name=name, headers={"X-CSRFToken": self.csrf},
                              catch_response=True) as r:
            if r.status_code in (402, 429):
                r.success()
            elif r.status_code >= 400:
                r.failure(f"{r.status_code}: {r.text[:120]}")

    @task(5)
    def analyze(self):
        if not CARS:
            return
        brand, series, engine = random.choice(CARS)
        self._post("/api/b2c/analyze", {
            "category": "otomobil", "brand": brand, "series": series, "engine": engine,
            "year": random.randrange(2012, 2024),
            "km": random.randrange(20, 250) * 1000, "price": random.randrange(500, 2500) * 1000,
            "city": random.choice(["Ankara", "İstanbul", "İzmir", ""]), "damage": [],
            "description": random.choice(["", "Hatasız boyasız, bakımlı araç.", "Değişensiz, tramer yok."]),
        }, "analyze")

    @task(3)
    def catalog(self):
        self.client.get("/api/b2c/vehicles", name="vehicles")

    @task(1)
    def locations(self):
        self.client.get("/api/b2c/locations", name="locations")

    @task(1)
    def me(self):
        self.client.get("/api/b2c/me", name="me")
