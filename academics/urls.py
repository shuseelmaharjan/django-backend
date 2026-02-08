from rest_framework.routers import DefaultRouter
from academics.views import AcademicClassViewSet, SectionViewSet, StudentEnrollmentViewSet

router = DefaultRouter()
router.register(r"classrooms", AcademicClassViewSet, basename="classroom")
router.register(r"sections", SectionViewSet, basename="section")
router.register(r"student-enrollments", StudentEnrollmentViewSet, basename="student-enrollment")

urlpatterns = router.urls
