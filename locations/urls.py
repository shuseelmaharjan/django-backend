from django.urls import path
from .views import (
    ProvinceListView,
    DistrictListView,
    MunicipalityListView,
    ProvinceTreeView
)

urlpatterns = [
    # Individual optimized endpoints
    path("v1/provinces/", ProvinceListView.as_view(), name="province-list"),
    path("v1/districts/", DistrictListView.as_view(), name="district-list"),
    path("v1/municipalities/", MunicipalityListView.as_view(), name="municipality-list"),

    # Full tree endpoint for backward compatibility
    path("v1/locations/", ProvinceTreeView.as_view(), name="province-tree"),
]
