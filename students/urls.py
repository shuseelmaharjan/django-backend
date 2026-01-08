from rest_framework.routers import DefaultRouter
from students.views import StudentViewSet, StudentGuardianViewSet, StudentAddressViewSet, StudentDocumentViewSet

router = DefaultRouter()
router.register(r"students", StudentViewSet, basename="students")
router.register(r"student-guardians", StudentGuardianViewSet, basename="student-guardians")
router.register(r"student-addresses", StudentAddressViewSet, basename="student-addresses")
router.register(r"student-documents", StudentDocumentViewSet, basename="student-documents")

urlpatterns = router.urls
