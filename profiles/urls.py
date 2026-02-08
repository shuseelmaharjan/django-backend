from rest_framework.routers import DefaultRouter
from .views import TeacherLevelViewSet, TeacherSpecializationViewSet

router = DefaultRouter()
router.register(r"teacher-levels", TeacherLevelViewSet, basename="teacher-level")
router.register(r"teacher-specializations", TeacherSpecializationViewSet, basename="teacher-specialization")

urlpatterns = router.urls
