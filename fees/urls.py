from rest_framework.routers import DefaultRouter
from fees.views import (
    FeeHeadViewSet, FeePlanViewSet, FeeRuleViewSet,
    StudentFeeOptionViewSet, StudentFeeOverrideViewSet,
    StudentChargeViewSet,
)

router = DefaultRouter()
router.register(r"v1/fee-heads", FeeHeadViewSet, basename="fee-heads")
router.register(r"v1/fee-plans", FeePlanViewSet, basename="fee-plans")
router.register(r"v1/fee-rules", FeeRuleViewSet, basename="fee-rules")
router.register(r"v1/student-options", StudentFeeOptionViewSet, basename="student-options")
router.register(r"v1/student-overrides", StudentFeeOverrideViewSet, basename="student-overrides")
router.register(r"v1/charges", StudentChargeViewSet, basename="charges")

urlpatterns = router.urls
