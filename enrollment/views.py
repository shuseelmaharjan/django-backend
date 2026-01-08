from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from enrollment.models import StudentEnrollment
from enrollment.serializers import (
    StudentEnrollmentSerializer,
    EnrollRequestSerializer,
    PromoteRequestSerializer,
)
from common.viewsets import SchoolScopedModelViewSet
from accounts.permissions import IsSchoolAdmin

@extend_schema(tags=["06. Enrollment & Promotion"])
class StudentEnrollmentViewSet(SchoolScopedModelViewSet):
    queryset = StudentEnrollment.objects.select_related(
        "student", "student__user", "academic_year", "academic_class", "section"
    ).all().order_by("-enrolled_on")
    serializer_class = StudentEnrollmentSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_queryset(self):
        qs = super().get_queryset()
        year = self.request.query_params.get("academic_year")
        cls = self.request.query_params.get("academic_class")
        sec = self.request.query_params.get("section")
        student = self.request.query_params.get("student")
        active = self.request.query_params.get("is_active")

        if year:
            qs = qs.filter(academic_year_id=year)
        if cls:
            qs = qs.filter(academic_class_id=cls)
        if sec:
            qs = qs.filter(section_id=sec)
        if student:
            qs = qs.filter(student_id=student)
        if active in ("true", "false"):
            qs = qs.filter(is_active=(active == "true"))

        return qs

    @action(detail=False, methods=["post"])
    def enroll(self, request):
        ser = EnrollRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        enrollment = ser.save()
        return Response(StudentEnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def promote(self, request):
        ser = PromoteRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        new_enr = ser.save()
        return Response(StudentEnrollmentSerializer(new_enr).data, status=status.HTTP_201_CREATED)
