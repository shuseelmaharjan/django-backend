from rest_framework.routers import DefaultRouter
from accounts.views_roles import RoleViewSet, RoleAssignmentViewSet

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="roles")
router.register(r"role-assignments", RoleAssignmentViewSet, basename="role-assignments")

urlpatterns = router.urls
