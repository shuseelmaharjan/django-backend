from rest_framework.routers import DefaultRouter
from staff.views_attendance import StaffAttendanceViewSet

router = DefaultRouter()
router.register(r"attendance", StaffAttendanceViewSet, basename="staff-attendance")

urlpatterns = router.urls
