from rest_framework.routers import DefaultRouter
from staff.views import StaffViewSet, TeacherProfileViewSet, TeacherAssignmentViewSet

router = DefaultRouter()
router.register(r"v1/staff", StaffViewSet, basename="staff")
router.register(r"v1/teachers", TeacherProfileViewSet, basename="teachers")
router.register(r"v1/teacher-assignments", TeacherAssignmentViewSet, basename="teacher-assignments")

urlpatterns = router.urls
