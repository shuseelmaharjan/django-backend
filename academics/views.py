from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from academics.models import AcademicClass, Section
from academics.serializers import (
    AcademicClassCreateSerializer, AcademicClassUpdateSerializer, AcademicClassReadSerializer,
    SectionCreateSerializer, SectionUpdateSerializer, SectionReadSerializer,
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

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return AcademicClass.objects.select_related("batch__school").filter(batch__school=school)

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
        return Response({"message": "Class created.", "data": AcademicClassReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

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
        return Response({"message": "Section created.", "data": SectionReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

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
