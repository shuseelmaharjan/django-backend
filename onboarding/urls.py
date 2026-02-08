# onboarding/urls.py
from rest_framework.routers import DefaultRouter
from .views import AdminOnboardingViewSet
from .staff_views import StaffUserViewSet
from .student_views import StudentUserViewSet

router = DefaultRouter()
router.register(r"admin", AdminOnboardingViewSet, basename="onboarding-admin")
router.register(r"staff-users", StaffUserViewSet, basename="staff-users")
router.register(r"students", StudentUserViewSet, basename="students")


urlpatterns = router.urls
