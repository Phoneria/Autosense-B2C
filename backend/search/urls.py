from django.urls import path

from .views import AnalyzeView, ListingTextView, LocationsView, VehicleDefaultsView, VehiclesView

urlpatterns = [
    path("b2c/vehicles", VehiclesView.as_view()),
    path("arabam-vehicles", VehiclesView.as_view()),
    path("b2c/locations", LocationsView.as_view()),
    path("b2c/vehicle-defaults", VehicleDefaultsView.as_view()),
    path("b2c/analyze", AnalyzeView.as_view()),
    path("b2c/lookup-text", ListingTextView.as_view()),
]
