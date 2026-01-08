from drf_spectacular.utils import extend_schema
from accounts.permissions import IsSchoolAdmin
from common.viewsets import SchoolScopedModelViewSet
from assessments.models import Subject
from assessments.serializers_subjects import SubjectSerializer


@extend_schema(tags=["12. Assessments (Subjects)"])
class SubjectViewSet(SchoolScopedModelViewSet):
    queryset = Subject.objects.all().order_by("name")
    serializer_class = SubjectSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_queryset(self):
        qs = super().get_queryset()
        include_inactive = (self.request.query_params.get("include_inactive") or "false").lower() == "true"
        if not include_inactive:
            qs = qs.filter(is_active=True)
        return qs
