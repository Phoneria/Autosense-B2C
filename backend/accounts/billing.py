"""Plan ve kredi yönetimi.

Ödeme entegrasyonu yok: plan değişikliği ve kredi ekleme anında onaylanır.
Her analiz 1 kredi harcar. Plan kredileri her 10 dakikada bir plan kotasına
yeniden doldurulur; eklenen ekstra krediler bu sıfırlamadan etkilenmez ve
plan kredisi bittikten sonra harcanır.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Subscription

# autosense-patch: daily-reset-v1
from zoneinfo import ZoneInfo
RESET_INTERVAL = timedelta(days=1)
RESET_TZ = ZoneInfo("Europe/Istanbul")


def _day_start(moment):
    """Verilen anın İstanbul saatine göre günün başlangıcı (00:00)."""
    local = timezone.localtime(moment, RESET_TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _next_reset(sub_or_start):
    start = getattr(sub_or_start, "period_start", sub_or_start)
    return _day_start(start) + RESET_INTERVAL


DEFAULT_PLAN = "basic"
PLANS = {
    "basic": {"name": "Basic", "credits": 3, "price_label": "Ücretsiz",
              "features": ["Günde 3 analiz", "Analiz sayfası"]},
    "pro": {"name": "Pro", "credits": 15, "price_label": "₺499 / ay",
            "features": ["Günde 15 analiz", "Ne olurdu? senaryoları",
                         "Değer kaybı ve tahmin detayları", "Araç Rehberi ve Bölgesel fırsatlar (özet)"]},
    "premium": {"name": "Premium", "credits": 50, "unlimited": True, "price_label": "₺2.999 / ay",
                "features": ["Sınırsız analiz", "Pro'daki her şey", "Yayındaki benzer ilanlar",
                             "Araç Rehberi model sayfası: fiyat/satış grafikleri, karşılaştırma",
                             "Bölgesel fırsatların arkasındaki gerçek ilanlar"]},
}

# Plan -> erişilebilen özellikler. Backend izinleri ve frontend sekmeleri bu tabloyu kullanır.
PLAN_FEATURES = {
    "basic": ["analysis"],
    "pro": ["analysis", "scenarios", "depreciation", "estimate_details",
            "guide", "regional"],
    "premium": ["analysis", "scenarios", "depreciation", "estimate_details",
                "guide", "regional", "similar_listings", "guide_model_detail", "regional_listings",
                "trait_sources"],
}
FEATURE_MIN_PLAN = {}
for _plan in ("premium", "pro", "basic"):
    for _feature in PLAN_FEATURES[_plan]:
        FEATURE_MIN_PLAN[_feature] = _plan


def plan_allows(plan: str, feature: str) -> bool:
    return feature in PLAN_FEATURES.get(plan, PLAN_FEATURES[DEFAULT_PLAN])


CREDIT_PACKS: dict[int, str] = {}  # ek kredi kaldırıldı


class NoCredits(Exception):
    pass


class PlanRequired(Exception):
    pass


def _apply_reset(sub: Subscription, now) -> bool:
    today = _day_start(now)
    if sub.period_start and _day_start(sub.period_start) >= today:
        return False
    sub.period_start = today
    sub.credits = PLANS.get(sub.plan, PLANS[DEFAULT_PLAN])["credits"]
    return True


def _locked(user) -> Subscription:
    now = timezone.now()
    sub, created = Subscription.objects.select_for_update().get_or_create(
        user=user,
        defaults={"plan": DEFAULT_PLAN, "credits": PLANS[DEFAULT_PLAN]["credits"], "period_start": now},
    )
    if not created and _apply_reset(sub, now):
        sub.save(update_fields=["credits", "period_start", "updated_at"])
    return sub


def serialize(sub: Subscription) -> dict:
    plan = PLANS.get(sub.plan, PLANS[DEFAULT_PLAN])
    return {
        "unlimited": bool(plan.get("unlimited")),
        "plan": sub.plan if sub.plan in PLANS else DEFAULT_PLAN,
        "plan_name": plan["name"],
        "quota": plan["credits"],
        "credits": sub.credits,
        "extra_credits": 0,
        "total_credits": sub.credits,
        "next_reset_at": _next_reset(sub).isoformat(),
        "reset_minutes": int(RESET_INTERVAL.total_seconds() // 60),
        "plan_features": PLAN_FEATURES.get(sub.plan, PLAN_FEATURES[DEFAULT_PLAN]),
    }


def catalog() -> dict:
    return {
        "plans": [{"id": key, **value} for key, value in PLANS.items()],
        "credit_packs": [{"amount": amount, "price_label": label} for amount, label in CREDIT_PACKS.items()],
    }


def status(user) -> dict:
    """SALT OKUMA. Her istekte (me, izin kontrolleri) çağrıldığı için tek bir
    yazma bile SQLite'ta eşzamanlı isteklerde "database is locked" hatasına
    yol açıyordu. Kayıt yoksa DB'ye yazılmaz -- varsayılan plan hesaplanır;
    yenilenme de bellekte uygulanır, kalıcı yazma ilk harcama/plan değişiminde
    (_locked) yapılır."""
    sub = Subscription.objects.filter(user=user).first()
    if sub is None:
        return serialize(Subscription(user=user, plan=DEFAULT_PLAN,
                                      credits=PLANS[DEFAULT_PLAN]["credits"],
                                      period_start=timezone.now()))
    _apply_reset(sub, timezone.now())          # kaydedilmez; sadece görüntü
    return serialize(sub)


def choose_plan(user, plan: str) -> dict:
    if plan not in PLANS:
        raise ValueError("Geçersiz plan.")
    with transaction.atomic():
        sub = _locked(user)
        if sub.plan != plan:
            sub.plan = plan
            sub.credits = PLANS[plan]["credits"]
            sub.period_start = timezone.now()
            sub.save()
        return serialize(sub)


def add_credits(user, amount: int) -> dict:
    raise PlanRequired("Ek kredi kaldırıldı. Krediler her gün 00:00'da yenilenir.")
    if amount not in CREDIT_PACKS:
        raise ValueError("Geçersiz kredi paketi.")
    with transaction.atomic():
        sub = _locked(user)
        if not plan_allows(sub.plan, "extra_credits"):
            raise PlanRequired("Ek kredi satın almak için Pro veya Premium plana geçin.")
        sub.extra_credits += amount
        sub.save(update_fields=["extra_credits", "updated_at"])
        return serialize(sub)


def consume(user) -> dict:
    """1 kredi harcar; kredi yoksa NoCredits fırlatır."""
    with transaction.atomic():
        sub = _locked(user)
        if PLANS.get(sub.plan, PLANS[DEFAULT_PLAN]).get("unlimited"):
            return {**serialize(sub), "_source": "unlimited"}
        if sub.credits > 0:
            sub.credits -= 1
            source = "plan"
        else:
            raise NoCredits(serialize(sub))
        sub.save(update_fields=["credits", "extra_credits", "updated_at"])
        return {**serialize(sub), "_source": source}


def refund(user, source: str) -> dict:
    """Analiz başarısız olursa harcanan krediyi geri verir."""
    if source == "unlimited":
        return status(user)
    with transaction.atomic():
        sub = _locked(user)
        if source == "extra":
            sub.extra_credits += 1
        else:
            quota = PLANS.get(sub.plan, PLANS[DEFAULT_PLAN])["credits"]
            sub.credits = min(quota, sub.credits + 1)
        sub.save(update_fields=["credits", "extra_credits", "updated_at"])
        return serialize(sub)
