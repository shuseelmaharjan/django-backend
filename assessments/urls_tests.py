from rest_framework.routers import DefaultRouter
from assessments.views_tests import OnlineTestViewSet

router = DefaultRouter()
router.register(r"online-tests", OnlineTestViewSet, basename="online-tests")
urlpatterns = router.urls
