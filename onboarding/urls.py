# onboarding/urls.py
from rest_framework.routers import DefaultRouter
from .views import AdminOnboardingViewSet

router = DefaultRouter()
router.register(r"admin", AdminOnboardingViewSet, basename="onboarding-admin")

urlpatterns = router.urls
