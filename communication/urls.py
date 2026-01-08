from rest_framework.routers import DefaultRouter
from communication.views import NoticeViewSet, MessageLogViewSet

router = DefaultRouter()
router.register(r"notices", NoticeViewSet, basename="notices")
router.register(r"message-logs", MessageLogViewSet, basename="message-logs")

urlpatterns = router.urls
