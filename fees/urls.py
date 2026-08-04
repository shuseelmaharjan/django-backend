from django.urls import path
from rest_framework.routers import DefaultRouter

from fees.views import FeeHeadViewSet, FeeStructureViewSet
from fees.views_applicable import FeeStructureApplicableAPIView
from fees.views_finance import (
    FeeAdvanceCreditViewSet,
    FeeConfigurationAPIView,
    FeeInvoiceViewSet,
    FeePaymentViewSet,
    StudentFeeAccountAPIView,
    StudentFeeConcessionViewSet,
)

router = DefaultRouter()
router.register(r"fee-heads", FeeHeadViewSet, basename="fee-head")
router.register(r"fee-structures", FeeStructureViewSet, basename="fee-structure")
router.register(r"fee-invoices", FeeInvoiceViewSet, basename="fee-invoice")
router.register(r"fee-payments", FeePaymentViewSet, basename="fee-payment")
router.register(r"fee-concessions", StudentFeeConcessionViewSet, basename="fee-concession")
router.register(r"fee-advances", FeeAdvanceCreditViewSet, basename="fee-advance")

urlpatterns = [
    path("fee-structures/applicable/", FeeStructureApplicableAPIView.as_view(), name="fee-structure-applicable"),
    path("fee-configuration/", FeeConfigurationAPIView.as_view(), name="fee-configuration"),
    path(
        "student-fee-accounts/<uuid:enrollment_id>/",
        StudentFeeAccountAPIView.as_view(),
        name="student-fee-account",
    ),
    *router.urls,
]
