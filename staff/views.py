from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from staff.models import StaffProfile, TeacherProfile, TeacherAssignment
from staff.serializers import (
    StaffProfileSerializer, StaffCreateSerializer,
    TeacherProfileSerializer, TeacherAssignmentSerializer
)
from common.viewsets import SchoolScopedModelViewSet
from accounts.permissions import IsSchoolAdmin


@extend_schema(tags=["07. Staff"])
class StaffViewSet(SchoolScopedModelViewSet):
    queryset = StaffProfile.objects.select_related("user").all().order_by("-created_at")
    serializer_class = StaffProfileSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_serializer_class(self):
        if self.action == "create":
            return StaffCreateSerializer
        return StaffProfileSerializer

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        staff = ser.save()
        return Response(StaffProfileSerializer(staff).data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        qs = super().get_queryset()
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(user__email__icontains=q) | qs.filter(user__phone__icontains=q) | qs.filter(employee_code__icontains=q)
        return qs


@extend_schema(tags=["07. Staff"])
class TeacherProfileViewSet(viewsets.ModelViewSet):
    queryset = TeacherProfile.objects.select_related("staff", "staff__user").all()
    serializer_class = TeacherProfileSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(staff__school_id=school_id)
        return qs


@extend_schema(tags=["07. Staff"])
class TeacherAssignmentViewSet(viewsets.ModelViewSet):
    queryset = TeacherAssignment.objects.select_related(
        "teacher", "teacher__staff", "teacher__staff__user",
        "academic_year", "academic_class", "section"
    ).all()
    serializer_class = TeacherAssignmentSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(academic_year__school_id=school_id)

        year = self.request.query_params.get("academic_year")
        cls = self.request.query_params.get("academic_class")
        if year:
            qs = qs.filter(academic_year_id=year)
        if cls:
            qs = qs.filter(academic_class_id=cls)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx
