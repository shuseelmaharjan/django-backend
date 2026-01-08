from rest_framework.routers import DefaultRouter
from enrollment.views import StudentEnrollmentViewSet

router = DefaultRouter()
router.register(r"enrollments", StudentEnrollmentViewSet, basename="enrollments")

urlpatterns = router.urls
