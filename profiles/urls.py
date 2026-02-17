from rest_framework.routers import DefaultRouter
from .views import TeacherLevelViewSet, TeacherSpecializationViewSet
from .views_teachers import TeacherListViewSet
from .views_student_list import StudentListViewSet
from .views_student_360 import Student360ViewSet
router = DefaultRouter()
router.register(r"teacher-levels", TeacherLevelViewSet, basename="teacher-level")
router.register(r"teacher-specializations", TeacherSpecializationViewSet, basename="teacher-specialization")
router.register(r"teachers", TeacherListViewSet, basename="teachers")
router.register(r"students-short-info", StudentListViewSet, basename="students")
router.register(r"students-360", Student360ViewSet, basename="students-360")



urlpatterns = router.urls
