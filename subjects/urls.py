# subjects/urls.py
from rest_framework.routers import DefaultRouter
from subjects.views import SubjectViewSet

router = DefaultRouter()
router.register(r"subjects", SubjectViewSet, basename="subject")

urlpatterns = router.urls
