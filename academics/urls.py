from rest_framework.routers import DefaultRouter
from academics.views import AcademicClassViewSet, SectionViewSet

router = DefaultRouter()
router.register(r"classrooms", AcademicClassViewSet, basename="classroom")
router.register(r"sections", SectionViewSet, basename="section")

urlpatterns = router.urls
