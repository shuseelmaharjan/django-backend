from rest_framework.routers import DefaultRouter
from exams.views import ExamViewSet, ExamSetViewSet

router = DefaultRouter()
router.register(r"exams", ExamViewSet, basename="exam")
router.register(r"exam-sets", ExamSetViewSet, basename="examset")

urlpatterns = router.urls