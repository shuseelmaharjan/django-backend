from rest_framework.routers import DefaultRouter
from .views import EcaActivityViewSet

router = DefaultRouter()
router.register(r"eca/activities", EcaActivityViewSet, basename="eca-activities")

urlpatterns = router.urls
