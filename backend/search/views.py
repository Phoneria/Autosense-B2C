import logging
import sqlite3

from django.db import DatabaseError
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from accounts.permissions import VerifiedUser
from accounts.features import has_feature
from .serializers import AnalysisSerializer, ListingTextSerializer, VehicleSerializer
from .services import b2c
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
    permission_classes = [VerifiedUser, FeaturePermission]
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
            return Response(b2c.analyze(serializer.validated_data))
        except (FileNotFoundError, sqlite3.Error, DatabaseError):
            logger.exception("B2C analysis reference data unavailable")
            return Response({"error": "Analiz verilerine şu anda ulaşılamıyor. Lütfen daha sonra tekrar deneyin."}, status=503)
        except ValueError:
            return Response({"error": "Araç bilgileri analiz edilemedi. Alanları kontrol edin."}, status=400)


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
