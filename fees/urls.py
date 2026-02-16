# fees/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter

from fees.views import FeeHeadViewSet, FeeStructureViewSet
from fees.views_applicable import FeeStructureApplicableAPIView

router = DefaultRouter()
router.register(r"fee-heads", FeeHeadViewSet, basename="fee-head")
router.register(r"fee-structures", FeeStructureViewSet, basename="fee-structure")

urlpatterns = [
    path("fee-structures/applicable/", FeeStructureApplicableAPIView.as_view(), name="fee-structure-applicable"),

    *router.urls,
]
