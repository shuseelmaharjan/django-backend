from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from accounts.models import Role, RoleAssignment
from accounts.serializers_roles import RoleSerializer, RoleAssignmentSerializer
from common.permissions import IsSuperUser


@extend_schema_view(
    list=extend_schema(tags=["03. Roles & Permissions"], summary="List roles"),
    retrieve=extend_schema(tags=["03. Roles & Permissions"], summary="Get role by id"),
    create=extend_schema(tags=["03. Roles & Permissions"], summary="Create role (superuser only)"),
    update=extend_schema(tags=["03. Roles & Permissions"], summary="Update role (superuser only)"),
    partial_update=extend_schema(tags=["03. Roles & Permissions"], summary="Patch role (superuser only)"),
    destroy=extend_schema(tags=["03. Roles & Permissions"], summary="Delete role (superuser only)"),
)
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all().order_by("school_id", "code")
    serializer_class = RoleSerializer
    permission_classes = [IsSuperUser]
    lookup_field = "id"

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            return Response(
                {"detail": "System roles cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            return Response(
                {"detail": "System roles cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            return Response(
                {"detail": "System roles cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(tags=["03. Roles & Permissions"], summary="List role assignments"),
    retrieve=extend_schema(tags=["03. Roles & Permissions"], summary="Get role assignment by id"),
    create=extend_schema(tags=["03. Roles & Permissions"], summary="Create role assignment (superuser only)"),
    update=extend_schema(tags=["03. Roles & Permissions"], summary="Update role assignment (superuser only)"),
    partial_update=extend_schema(tags=["03. Roles & Permissions"], summary="Patch role assignment (superuser only)"),
    destroy=extend_schema(tags=["03. Roles & Permissions"], summary="Delete role assignment (superuser only)"),
)
class RoleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = RoleAssignment.objects.select_related("user", "role").all().order_by("-created_at")
    serializer_class = RoleAssignmentSerializer
    permission_classes = [IsSuperUser]
    lookup_field = "id"

    def get_queryset(self):
        """
        Optional filters for admin UI:
        /role-assignments/?user=<uuid>&role=<uuid>&school_id=<str>
        """
        qs = super().get_queryset()

        user_id = self.request.query_params.get("user")
        role_id = self.request.query_params.get("role")
        school_id = self.request.query_params.get("school_id")

        if user_id:
            qs = qs.filter(user_id=user_id)
        if role_id:
            qs = qs.filter(role_id=role_id)
        if school_id:
            # RoleAssignment doesn't have school_id, so filter via role.school_id
            qs = qs.filter(role__school_id__in=[school_id, "*"])

        return qs
