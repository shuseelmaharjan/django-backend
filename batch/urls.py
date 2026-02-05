from rest_framework.routers import DefaultRouter
from .views import AcademicBatchViewSet

router = DefaultRouter()
router.register(r"batches", AcademicBatchViewSet, basename="academic-batch")

urlpatterns = router.urls
