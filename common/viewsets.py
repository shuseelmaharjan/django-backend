from rest_framework import viewsets
from common.school import get_school_id_from_request

class SchoolScopedModelViewSet(viewsets.ModelViewSet):
    """
    Base viewset:
    - requires X-School-Id for all requests
    - filters queryset by school_id (for models that have a school_id field)
    - sets school_id on create automatically
    """

    school_field = "school_id"  # override per model if needed
    require_school_header = True

    def initial(self, request, *args, **kwargs):
        request.school_id = get_school_id_from_request(request, required=self.require_school_header)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id and self.school_field:
            qs = qs.filter(**{self.school_field: school_id})
        return qs

    def perform_create(self, serializer):
        school_id = getattr(self.request, "school_id", None)
        if school_id and self.school_field:
            serializer.save(**{self.school_field: school_id})
        else:
            serializer.save()
