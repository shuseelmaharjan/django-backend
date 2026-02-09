from rest_framework.routers import DefaultRouter
from .views import TeacherLevelViewSet, TeacherSpecializationViewSet
from .views_teachers import TeacherListViewSet

router = DefaultRouter()
router.register(r"teacher-levels", TeacherLevelViewSet, basename="teacher-level")
router.register(r"teacher-specializations", TeacherSpecializationViewSet, basename="teacher-specialization")
router.register(r"teachers", TeacherListViewSet, basename="teachers")

urlpatterns = router.urls
