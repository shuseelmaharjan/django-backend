from rest_framework.routers import DefaultRouter
from academics.views import AcademicYearViewSet, AcademicClassViewSet, SectionViewSet

router = DefaultRouter()
router.register(r"years", AcademicYearViewSet, basename="academic-years")
router.register(r"classes", AcademicClassViewSet, basename="academic-classes")
router.register(r"sections", SectionViewSet, basename="sections")

urlpatterns = router.urls
