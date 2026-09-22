import logging
import sqlite3

from django.db import DatabaseError
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from accounts.permissions import PlanFeature, VerifiedUser
from accounts.features import has_feature
from accounts import billing
from .serializers import AnalysisSerializer, CostSerializer, ListingTextSerializer, ScenarioSerializer, VehicleSerializer
from .services import b2c, guide, regional, vehicle_traits
from .services.arabam_vehicles_service import load_arabam_vehicles
from .services.listing_url_lookup import ListingLookupError, parse_pasted_listing_text

logger = logging.getLogger(__name__)


class AnalysisThrottle(UserRateThrottle):
    rate = "20/min"
    scope = "b2c_analysis"


class LookupThrottle(UserRateThrottle):
    rate = "30/min"
    scope = "b2c_lookup"


class ReadThrottle(UserRateThrottle):
    rate = "120/min"
    scope = "b2c_read"


class FeaturePermission(BasePermission):
    message = "Bu özellik hesabınız için kullanılamıyor."
    code = "feature_unavailable"

    def has_permission(self, request, view):
        return has_feature(request.user, getattr(view, "feature", ""))


class ProtectedView(APIView):
    permission_classes = [VerifiedUser, FeaturePermission, PlanFeature]
    plan_feature: str | None = None
    throttle_classes = [ReadThrottle]


class VehiclesView(ProtectedView):
    feature = "vehicle_options"
    def get(self, request):
        return Response(load_arabam_vehicles())


class LocationsView(ProtectedView):
    feature = "locations"
    def get(self, request):
        return Response(b2c.load_locations())


class VehicleDefaultsView(ProtectedView):
    feature = "vehicle_defaults"
    def post(self, request):
        serializer = VehicleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(b2c.vehicle_defaults(**serializer.validated_data))


class AnalyzeView(ProtectedView):
    feature = "analysis"
    throttle_classes = [AnalysisThrottle]

    def post(self, request):
        serializer = AnalysisSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            spent = billing.consume(request.user)
        except billing.NoCredits as exc:
            return Response({
                "error": "Krediniz bitti. Kredileriniz birkaç dakika içinde yenilenecek; "
                         "beklemek istemiyorsanız Profil sayfasından kredi ekleyebilir veya planınızı yükseltebilirsiniz.",
                "code": "no_credits", "billing": exc.args[0],
            }, status=402)
        source = spent.pop("_source")
        plan = _plan(request.user)
        try:
            result = b2c.analyze_cached(serializer.validated_data)
        except (FileNotFoundError, sqlite3.Error, DatabaseError):
            logger.exception("B2C analysis reference data unavailable")
            billing.refund(request.user, source)
            return Response({"error": "Analiz verilerine şu anda ulaşılamıyor. Lütfen daha sonra tekrar deneyin."}, status=503)
        except ValueError:
            billing.refund(request.user, source)
            return Response({"error": "Araç bilgileri analiz edilemedi. Alanları kontrol edin."}, status=400)
        return Response({**_apply_plan_gates(result, plan), "billing": spent, "plan": plan})


def _apply_plan_gates(result: dict, plan: str) -> dict:
    """Plana göre kilitli bölümlerin VERİSİNİ hiç göndermez; yerine sadece
    "kaç kayıt var + hangi plan gerekiyor" bilgisini koyar. Blur arayüzde
    iskelet üzerinden yapılır -- gerçek veriyi gönderip CSS ile bulanıklaştırmak
    tarayıcıdan okunabilirdi."""
    locks: dict = {}

    if not billing.plan_allows(plan, "similar_listings"):
        locks["similar_listings"] = _lock("similar_listings", plan, len(result.get("similar_listings") or []))
        result["similar_listings"] = []

    if not billing.plan_allows(plan, "depreciation"):
        locks["depreciation"] = _lock("depreciation", plan)
        result["depreciation"] = {"available": False, "reason": "", "note": "", "current_value": None,
                                  "one_year_value": None, "one_year_loss": None,
                                  "three_year_value": None, "three_year_loss": None}

    if not billing.plan_allows(plan, "estimate_details"):
        evidence = result.get("evidence") or {}
        locks["estimate_details"] = _lock("estimate_details", plan, evidence.get("unique_comparables"))
        result["evidence"] = {"strength": evidence.get("strength", "medium"), "locked": True}
        result["data_sources"] = None

    if not billing.plan_allows(plan, "trait_sources"):
        traits = result.get("vehicle_traits")
        if traits:
            locks["trait_sources"] = _lock("trait_sources", plan)
            for tip in ("kronik", "iyi", "kotu"):
                for kayit in traits.get(tip) or []:
                    kayit["kaynak_url"] = None
                    kayit["kaynak_alan"] = None
                    kayit["kaynak_alinti"] = None

    result["locks"] = locks
    return result


class ScenarioView(ProtectedView):
    """Ne olurdu? senaryosu: yalnızca fiyat tahmini + karar + pazarlık. Kredi harcamaz. Pro+."""
    feature = "analysis"
    plan_feature = "scenarios"
    throttle_classes = [LookupThrottle]

    def post(self, request):
        serializer = ScenarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(b2c.scenario(serializer.validated_data))
        except (FileNotFoundError, sqlite3.Error, DatabaseError):
            logger.exception("B2C scenario reference data unavailable")
            return Response({"error": "Analiz verilerine şu anda ulaşılamıyor. Lütfen daha sonra tekrar deneyin."}, status=503)
        except ValueError:
            return Response({"error": "Senaryo hesaplanamadı. Alanları kontrol edin."}, status=400)


class CostView(ProtectedView):
    """Kişiselleştirilmiş yıllık sahip olma maliyeti. Kredi harcamaz. Pro+ (arayüzde şu an kullanılmıyor)."""
    feature = "analysis"
    plan_feature = "scenarios"
    throttle_classes = [LookupThrottle]

    def post(self, request):
        serializer = CostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from .services.tco import compute_personal_tco
        return Response(compute_personal_tco(**serializer.validated_data))


class RegionalDealsView(ProtectedView):
    """Premium/Pro: hangi model hangi ilde ülke geneline göre daha uygun.

    İlanlar (her satırın arkasındaki gerçek ilanlar) yalnızca Premium'da döner.
    """
    feature = "regional_deals"
    plan_feature = "regional"
    throttle_classes = [ReadThrottle]

    def get(self, request):
        plan = _plan(request.user)
        try:
            data = regional.overview()
        except (FileNotFoundError, sqlite3.Error, DatabaseError):
            logger.exception("Regional deals data unavailable")
            return Response({"error": "Bölgesel veriye şu anda ulaşılamıyor."}, status=503)
        if not billing.plan_allows(plan, "regional_listings"):
            data = dict(data, deals=[{**d, "top_listings": []} for d in data["deals"]],
                        listings_lock=_lock("regional_listings", plan))
        return Response(data)


def _plan(user) -> str:
    return billing.status(user)["plan"]


def _lock(feature: str, plan: str, count=None) -> dict:
    """Kilitli bölüm için arayüze gereken bilgi: mevcut plan + gereken plan."""
    required = billing.FEATURE_MIN_PLAN.get(feature, "premium")
    return {
        "feature": feature,
        "required_plan": required,
        "required_plan_name": billing.PLANS[required]["name"],
        "current_plan": plan,
        "current_plan_name": billing.PLANS.get(plan, billing.PLANS["basic"])["name"],
        "count": count,
    }


class GuideView(ProtectedView):
    """Araç Rehberi ana sayfası + model listesi (Pro+)."""
    feature = "vehicle_guide"
    plan_feature = "guide"

    def get(self, request):
        try:
            plan = _plan(request.user)
            return Response({**guide.home(billing.plan_allows(plan, "guide_model_detail")), "plan": plan})
        except (FileNotFoundError, sqlite3.Error, DatabaseError):
            logger.exception("Vehicle guide data unavailable")
            return Response({"error": "Araç rehberi verisine şu anda ulaşılamıyor."}, status=503)


class GuideModelView(ProtectedView):
    """Model sayfası (Pro+). Haftalık grafikler ve benzer modeller yalnızca Premium'da döner."""
    feature = "vehicle_guide"
    plan_feature = "guide"

    def get(self, request):
        key = (request.query_params.get("key") or "").strip()
        plan = _plan(request.user)
        detailed = billing.plan_allows(plan, "guide_model_detail")
        data = guide.model(key, detailed) if key else None
        if data is None:
            return Response({"error": "Model bulunamadı."}, status=404)
        if not detailed:
            # Pro: model sayfasının kendisi kilitli -- yalnızca kimlik bilgisi
            # ve ana sayfada zaten görünen sayılar döner.
            data = {"key": data["key"], "name": data["name"], "category": data["category"],
                    "active": data["active"], "removed_30d": data["removed_30d"],
                    "snapshot_date": data["snapshot_date"], "premium": False,
                    "trait_engines": [], "lock": _lock("guide_model_detail", plan, data["active"])}
        return Response(data)


class GuideCompareView(ProtectedView):
    """Premium: en fazla 3 modeli aynı grafikte karşılaştırma."""
    feature = "vehicle_guide"
    plan_feature = "guide_model_detail"

    def get(self, request):
        keys = [k.strip() for k in (request.query_params.get("keys") or "").split(",") if k.strip()][:3]
        if not keys:
            return Response({"error": "En az bir model seçin."}, status=400)
        return Response(guide.compare(keys))


class VehicleTraitsView(ProtectedView):
    """Araç kronik / iyi / kötü özellikleri.

    `?key=` verilmezse seçim kutusu için araç listesini döner; verilirse o
    aracın özelliklerini. Salt okuma, hız sınırı okuma sınıfıyla aynı.
    """
    feature = "vehicle_traits"
    throttle_classes = [ReadThrottle]

    def get(self, request):
        key = (request.query_params.get("key") or "").strip()
        if not key:
            return Response({"vehicles": vehicle_traits.arac_listesi()})
        return Response(vehicle_traits.arac_ozellikleri(key))


class ListingTextView(ProtectedView):
    feature = "lookup_text"
    throttle_classes = [LookupThrottle]

    def post(self, request):
        serializer = ListingTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(parse_pasted_listing_text(serializer.validated_data["text"]))
        except ListingLookupError as exc:
            return Response({"error": str(exc)}, status=400)
