# fees/urls.py
from rest_framework.routers import DefaultRouter
from .views import FeeHeadViewSet, FeeStructureViewSet

router = DefaultRouter()
router.register(r"fee-heads", FeeHeadViewSet, basename="fee-head")
router.register(r"fee-structures", FeeStructureViewSet, basename="fee-structure")


urlpatterns = router.urls
