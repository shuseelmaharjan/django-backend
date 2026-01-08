from rest_framework.routers import DefaultRouter
from assessments.views_core import QuestionBankViewSet, QuestionViewSet, QuestionChoiceViewSet

router = DefaultRouter()
router.register(r"question-banks", QuestionBankViewSet, basename="question-banks")
router.register(r"questions", QuestionViewSet, basename="questions")
router.register(r"question-choices", QuestionChoiceViewSet, basename="question-choices")

urlpatterns = router.urls
