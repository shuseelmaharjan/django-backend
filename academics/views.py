# academics/views.py
from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.models import AcademicClass, Section
from academics.serializers import (
    AcademicClassCreateSerializer, AcademicClassUpdateSerializer, AcademicClassReadSerializer,
    AcademicClassReorderSerializer,
    SectionCreateSerializer, SectionUpdateSerializer, SectionReadSerializer,
    SectionReorderSerializer,
)
from common.permissions import IsSchoolAdmin
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
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
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
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
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
