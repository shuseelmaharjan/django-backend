from rest_framework.routers import DefaultRouter
from academics.views import AcademicClassViewSet, SectionViewSet, StudentEnrollmentViewSet, ScheduleViewSet

router = DefaultRouter()
router.register(r"classrooms", AcademicClassViewSet, basename="classroom")
router.register(r"sections", SectionViewSet, basename="section")
router.register(r"student-enrollments", StudentEnrollmentViewSet, basename="student-enrollment")
router.register(r"schedules", ScheduleViewSet, basename="schedule")

urlpatterns = router.urls
