from django.urls import path
from .views import ProvinceListAPI, DistrictListAPI, MunicipalityListAPI

urlpatterns = [
    path("provinces/", ProvinceListAPI.as_view(), name="province-list"),
    path("districts/", DistrictListAPI.as_view(), name="district-list"),
    path("municipalities/", MunicipalityListAPI.as_view(), name="municipality-list"),
]
