from rest_framework.routers import DefaultRouter
from assessments.views_subjects import SubjectViewSet

router = DefaultRouter()
router.register(r"subjects", SubjectViewSet, basename="subjects")
urlpatterns = router.urls
