from rest_framework.routers import DefaultRouter
from organization.views import SchoolViewSet, SchoolSettingViewSet

router = DefaultRouter()
router.register(r"schools", SchoolViewSet, basename="schools")
router.register(r"school-settings", SchoolSettingViewSet, basename="school-settings")

urlpatterns = router.urls
