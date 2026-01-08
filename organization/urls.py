from rest_framework.routers import DefaultRouter
from organization.views import SchoolViewSet, CampusViewSet, SchoolSettingViewSet

router = DefaultRouter()
router.register(r"schools", SchoolViewSet, basename="schools")
router.register(r"campuses", CampusViewSet, basename="campuses")
router.register(r"school-settings", SchoolSettingViewSet, basename="school-settings")

urlpatterns = router.urls
