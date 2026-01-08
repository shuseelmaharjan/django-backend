from rest_framework import viewsets
from accounts.models import Role, RoleAssignment
from accounts.serializers_roles import RoleSerializer, RoleAssignmentSerializer
from accounts.permissions import IsSchoolAdmin
from common.viewsets import SchoolScopedModelViewSet
from drf_spectacular.utils import extend_schema

@extend_schema(tags=["03. Roles & Permissions"])
class RoleViewSet(SchoolScopedModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

@extend_schema(tags=["03. Roles & Permissions"])
class RoleAssignmentViewSet(viewsets.ModelViewSet):
    """
    Admin-only. Uses X-School-Id to help filtering (optional).
    Note: RoleAssignment model doesn’t store school_id, so we can’t auto-filter perfectly.
    """
    queryset = RoleAssignment.objects.select_related("user", "role").all().order_by("-created_at")
    serializer_class = RoleAssignmentSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(role__school_id__in=[school_id, "*"])
        return qs
