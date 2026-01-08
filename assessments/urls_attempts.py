from rest_framework.routers import DefaultRouter
from assessments.views_attempts import AttemptViewSet

router = DefaultRouter()
router.register(r"attempts", AttemptViewSet, basename="attempts")
urlpatterns = router.urls
