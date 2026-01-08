from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from students.models import StudentProfile, StudentGuardian, StudentAddress, StudentDocument
from students.serializers import (
    StudentProfileSerializer, StudentCreateSerializer,
    StudentGuardianSerializer, StudentAddressSerializer, StudentDocumentSerializer
)
from common.viewsets import SchoolScopedModelViewSet
from accounts.permissions import IsSchoolAdmin

@extend_schema(tags=["05. Students (Admission)"])
class StudentViewSet(SchoolScopedModelViewSet):
    queryset = StudentProfile.objects.select_related("user").all().order_by("-created_at")
    serializer_class = StudentProfileSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_serializer_class(self):
        if self.action == "create":
            return StudentCreateSerializer
        return StudentProfileSerializer

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        profile = ser.save()
        out = StudentProfileSerializer(profile).data
        return Response(out, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        qs = super().get_queryset()
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                user__email__icontains=q
            ) | qs.filter(
                user__phone__icontains=q
            ) | qs.filter(
                user__first_name__icontains=q
            ) | qs.filter(
                user__last_name__icontains=q
            )
        return qs

@extend_schema(tags=["05. Students (Admission)"])
class StudentGuardianViewSet(viewsets.ModelViewSet):
    queryset = StudentGuardian.objects.select_related("student", "guardian_user").all()
    serializer_class = StudentGuardianSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(student__school_id=school_id)
        student_id = self.request.query_params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs

@extend_schema(tags=["05. Students (Admission)"])
class StudentAddressViewSet(viewsets.ModelViewSet):
    queryset = StudentAddress.objects.select_related("student").all()
    serializer_class = StudentAddressSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(student__school_id=school_id)
        student_id = self.request.query_params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs

@extend_schema(tags=["05. Students (Admission)"])
class StudentDocumentViewSet(viewsets.ModelViewSet):
    queryset = StudentDocument.objects.select_related("student").all()
    serializer_class = StudentDocumentSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(student__school_id=school_id)
        student_id = self.request.query_params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs

    @action(detail=True, methods=["post"])
    def verify(self, request, id=None):
        doc = self.get_object()
        doc.is_verified = True
        doc.save(update_fields=["is_verified"])
        return Response({"detail": "Verified"}, status=status.HTTP_200_OK)
