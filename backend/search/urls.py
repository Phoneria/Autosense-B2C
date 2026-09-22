from django.urls import path

from .views import (AnalyzeView, CostView, GuideCompareView, GuideModelView, GuideView, ListingTextView, LocationsView, RegionalDealsView, ScenarioView,
                    VehicleDefaultsView, VehicleTraitsView, VehiclesView)

urlpatterns = [
    path("b2c/vehicles", VehiclesView.as_view()),
    path("arabam-vehicles", VehiclesView.as_view()),
    path("b2c/locations", LocationsView.as_view()),
    path("b2c/vehicle-defaults", VehicleDefaultsView.as_view()),
    path("b2c/analyze", AnalyzeView.as_view()),
    path("b2c/scenario", ScenarioView.as_view()),
    path("b2c/cost", CostView.as_view()),
    path("b2c/regional-deals", RegionalDealsView.as_view()),
    path("b2c/guide", GuideView.as_view()),
    path("b2c/guide/model", GuideModelView.as_view()),
    path("b2c/guide/compare", GuideCompareView.as_view()),
    path("b2c/lookup-text", ListingTextView.as_view()),
    path("b2c/vehicle-traits", VehicleTraitsView.as_view()),
]
