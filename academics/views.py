from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from academics.models import AcademicYear, AcademicClass, Section
from academics.serializers import AcademicYearSerializer, AcademicClassSerializer, SectionSerializer
from common.viewsets import SchoolScopedModelViewSet
from accounts.permissions import IsSchoolAdmin

@extend_schema(tags=["04. Academic Setup"])
class AcademicYearViewSet(SchoolScopedModelViewSet):
    queryset = AcademicYear.objects.all().order_by("-start_date")
    serializer_class = AcademicYearSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    @action(detail=True, methods=["post"])
    def set_active(self, request, id=None):
        school_id = request.school_id
        year = self.get_object()

        with transaction.atomic():
            AcademicYear.objects.filter(school_id=school_id, is_active=True).exclude(id=year.id).update(is_active=False)
            year.is_active = True
            year.save(update_fields=["is_active"])

        return Response({"detail": f"{year.name} set as active."}, status=status.HTTP_200_OK)

@extend_schema(tags=["04. Academic Setup"])
class AcademicClassViewSet(SchoolScopedModelViewSet):
    queryset = AcademicClass.objects.select_related("academic_year").all()
    serializer_class = AcademicClassSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_queryset(self):
        qs = super().get_queryset()
        ay = self.request.query_params.get("academic_year")
        if ay:
            qs = qs.filter(academic_year_id=ay)
        return qs

@extend_schema(tags=["04. Academic Setup"])
class SectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.select_related("academic_class", "academic_class__academic_year").all()
    serializer_class = SectionSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        # enforce X-School-Id scoping through joins
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(academic_class__school_id=school_id)

        class_id = self.request.query_params.get("academic_class")
        if class_id:
            qs = qs.filter(academic_class_id=class_id)
        return qs
