from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsSchoolAdmin, IsAuthenticatedReadOnlyOrAdmin
from organization.models import School, Campus, SchoolSetting
from organization.serializers import SchoolSerializer, CampusSerializer, SchoolSettingSerializer
from drf_spectacular.utils import extend_schema

@extend_schema(tags=["02. Organization"])
class SchoolViewSet(viewsets.ModelViewSet):
    """
    Schools are not scoped by X-School-Id because you need to bootstrap.
    Rule:
    - authenticated users can list/view
    - only admins/superusers can create/update (you can tighten this)
    """
    queryset = School.objects.all().order_by("-created_at")
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticatedReadOnlyOrAdmin]
    lookup_field = "id"

@extend_schema(tags=["02. Organization"])
class CampusViewSet(viewsets.ModelViewSet):
    queryset = Campus.objects.select_related("school").all()
    serializer_class = CampusSerializer
    permission_classes = [IsAuthenticatedReadOnlyOrAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.query_params.get("school")
        if school_id:
            qs = qs.filter(school_id=school_id)
        return qs

@extend_schema(tags=["02. Organization"])
class SchoolSettingViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    queryset = SchoolSetting.objects.select_related("school").all()
    serializer_class = SchoolSettingSerializer
    permission_classes = [IsAuthenticatedReadOnlyOrAdmin]
    lookup_field = "id"
