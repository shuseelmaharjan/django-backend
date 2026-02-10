# academics/views.py
from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import mixins, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from academics.models import AcademicClass, Section, StudentEnrollments
from academics.serializers import (
    AcademicClassCreateSerializer, AcademicClassUpdateSerializer, AcademicClassReadSerializer,
    AcademicClassReorderSerializer,
    SectionCreateSerializer, SectionUpdateSerializer, SectionReadSerializer,
    SectionReorderSerializer, StudentEnrollmentCreateSerializer, StudentEnrollmentUpdateSerializer, StudentEnrollmentReadSerializer,
    ScheduleCreateSerializer,
    ScheduleUpdateSerializer,
    ScheduleReadSerializer,
)
from common.permissions import IsSchoolAdmin, IsAuthenticatedAndActive
from utils.get_school_id_by_token import get_school_for_user


@extend_schema_view(
    list=extend_schema(tags=["Classroom"]),
    create=extend_schema(tags=["Classroom"], request=AcademicClassCreateSerializer),
    retrieve=extend_schema(tags=["Classroom"]),
    update=extend_schema(tags=["Classroom"], request=AcademicClassUpdateSerializer),
    partial_update=extend_schema(tags=["Classroom"], request=AcademicClassUpdateSerializer),
    destroy=extend_schema(tags=["Classroom"]),
)
class AcademicClassViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolAdmin]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code", "batch"]
    ordering_fields = ["name", "code", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        qs = AcademicClass.objects.select_related("batch__school").filter(batch__school=school)

        batch_id = (self.request.query_params.get("batch") or "").strip()
        if batch_id:
            qs = qs.filter(batch_id=batch_id)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return AcademicClassCreateSerializer
        if self.action in ("update", "partial_update"):
            return AcademicClassUpdateSerializer
        return AcademicClassReadSerializer

    def create(self, request, *args, **kwargs):
        s = AcademicClassCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Class created.", "data": AcademicClassReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = AcademicClassUpdateSerializer(instance=obj, data=request.data, partial=False)
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Class updated.", "data": AcademicClassReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = AcademicClassUpdateSerializer(instance=obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Class updated.", "data": AcademicClassReadSerializer(obj).data})

    @extend_schema(tags=["Classroom"], request=AcademicClassReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        s = AcademicClassReorderSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response({"message": "Classrooms reordered.", "data": result}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["Section"]),
    create=extend_schema(tags=["Section"], request=SectionCreateSerializer),
    retrieve=extend_schema(tags=["Section"]),
    update=extend_schema(tags=["Section"], request=SectionUpdateSerializer),
    partial_update=extend_schema(tags=["Section"], request=SectionUpdateSerializer),
    destroy=extend_schema(tags=["Section"]),
)
class SectionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolAdmin]
    lookup_field = "pk"

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Section.objects
            .select_related("academic_class__batch__school")
            .filter(academic_class__batch__school=school)
        )

    def get_serializer_class(self):
        if self.action == "create":
            return SectionCreateSerializer
        if self.action in ("update", "partial_update"):
            return SectionUpdateSerializer
        return SectionReadSerializer

    def create(self, request, *args, **kwargs):
        s = SectionCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Section created.", "data": SectionReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = SectionUpdateSerializer(instance=obj, data=request.data, partial=False)
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Section updated.", "data": SectionReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = SectionUpdateSerializer(instance=obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Section updated.", "data": SectionReadSerializer(obj).data})

    @extend_schema(tags=["Section"], request=SectionReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        s = SectionReorderSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response({"message": "Sections reordered.", "data": result}, status=status.HTTP_200_OK)

@extend_schema_view(
    list=extend_schema(tags=["Student Enrollment"]),
    create=extend_schema(tags=["Student Enrollment"], request=StudentEnrollmentCreateSerializer),
    retrieve=extend_schema(tags=["Student Enrollment"]),
    update=extend_schema(tags=["Student Enrollment"], request=StudentEnrollmentUpdateSerializer),
    partial_update=extend_schema(tags=["Student Enrollment"], request=StudentEnrollmentUpdateSerializer),
    destroy=extend_schema(tags=["Student Enrollment"]),
)
class StudentEnrollmentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolAdmin]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["student__first_name", "student__last_name", "student__phone", "student__email"]
    ordering_fields = ["enrolled_at", "status"]
    ordering = ["-enrolled_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        qs = (
            StudentEnrollments.objects
            .select_related("batch__school", "student", "academic_class", "section")
            .filter(batch__school=school)
        )

        batch_id = (self.request.query_params.get("batch") or "").strip()
        if batch_id:
            qs = qs.filter(batch_id=batch_id)

        class_id = (self.request.query_params.get("academic_class") or "").strip()
        if class_id:
            qs = qs.filter(academic_class_id=class_id)

        section_id = (self.request.query_params.get("section") or "").strip()
        if section_id:
            qs = qs.filter(section_id=section_id)

        student_id = (self.request.query_params.get("student") or "").strip()
        if student_id:
            qs = qs.filter(student_id=student_id)

        status_q = (self.request.query_params.get("status") or "").strip()
        if status_q:
            qs = qs.filter(status=status_q)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return StudentEnrollmentCreateSerializer
        if self.action in ("update", "partial_update"):
            return StudentEnrollmentUpdateSerializer
        return StudentEnrollmentReadSerializer

    def create(self, request, *args, **kwargs):
        s = StudentEnrollmentCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Enrollment created.", "data": StudentEnrollmentReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = StudentEnrollmentUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Enrollment updated.", "data": StudentEnrollmentReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = StudentEnrollmentUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Enrollment updated.", "data": StudentEnrollmentReadSerializer(obj).data})


@extend_schema_view(
    list=extend_schema(
        tags=["Schedule"],
        parameters=[
            OpenApiParameter(name="batch", required=False, type=str, description="Batch ID"),
            OpenApiParameter(name="academic_class", required=False, type=str, description="Class UUID"),
            OpenApiParameter(name="section", required=False, type=str, description="Section UUID"),
            OpenApiParameter(name="teacher", required=False, type=str, description="Teacher UUID"),
            OpenApiParameter(name="day_of_week", required=False, type=int, description="0=Mon..6=Sun"),
            OpenApiParameter(name="search", required=False, type=str, description="Search class/subject/teacher"),
            OpenApiParameter(name="ordering", required=False, type=str, description="ordering fields"),
        ],
    ),
    create=extend_schema(tags=["Schedule"], request=ScheduleCreateSerializer),
    retrieve=extend_schema(tags=["Schedule"]),
    update=extend_schema(tags=["Schedule"], request=ScheduleUpdateSerializer),
    partial_update=extend_schema(tags=["Schedule"], request=ScheduleUpdateSerializer),
    destroy=extend_schema(tags=["Schedule"]),
)
class ScheduleViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolAdmin]
    lookup_field = "pk"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "academic_class__name",
        "section__name",
        "subject__name",
        "subject__code",
        "teacher__first_name",
        "teacher__last_name",
        "teacher__phone",
        "teacher__email",
    ]
    ordering_fields = [
        "day_of_week",
        "start_time",
        "end_time",
        "academic_class__name",
        "subject__name",
        "teacher__first_name",
    ]
    ordering = ["day_of_week", "start_time"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        qs = (
            Schedule.objects
            .select_related(
                "batch__school",
                "academic_class",
                "section",
                "subject",
                "teacher",
            )
            .filter(batch__school=school)
        )

        batch_id = (self.request.query_params.get("batch") or "").strip()
        if batch_id:
            qs = qs.filter(batch_id=batch_id)

        class_id = (self.request.query_params.get("academic_class") or "").strip()
        if class_id:
            qs = qs.filter(academic_class_id=class_id)

        section_id = (self.request.query_params.get("section") or "").strip()
        if section_id:
            qs = qs.filter(section_id=section_id)

        teacher_id = (self.request.query_params.get("teacher") or "").strip()
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)

        day = (self.request.query_params.get("day_of_week") or "").strip()
        if day != "":
            try:
                qs = qs.filter(day_of_week=int(day))
            except ValueError:
                qs = qs.none()

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return ScheduleCreateSerializer
        if self.action in ("update", "partial_update"):
            return ScheduleUpdateSerializer
        return ScheduleReadSerializer

    def create(self, request, *args, **kwargs):
        s = ScheduleCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Schedule created.", "data": ScheduleReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = ScheduleUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Schedule updated.", "data": ScheduleReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = ScheduleUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Schedule updated.", "data": ScheduleReadSerializer(obj).data})