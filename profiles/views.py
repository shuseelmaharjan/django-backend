from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets, filters
from rest_framework.response import Response

from common.permissions import IsPlatformSuperAdmin, IsAuthenticatedAndActive
from .models import TeacherLevel, TeacherLevelStatus, TeacherSpecialization
from .serializers import (
    TeacherLevelCreateSerializer,
    TeacherLevelUpdateSerializer,
    TeacherLevelReadSerializer,
    TeacherSpecializationReadSerializer,
    TeacherSpecializationWriteSerializer,
)



@extend_schema_view(
    list=extend_schema(tags=["Teacher Level"]),
    create=extend_schema(tags=["Teacher Level"], request=TeacherLevelCreateSerializer),
    retrieve=extend_schema(tags=["Teacher Level"]),
    update=extend_schema(tags=["Teacher Level"], request=TeacherLevelUpdateSerializer),
    partial_update=extend_schema(tags=["Teacher Level"], request=TeacherLevelUpdateSerializer),
    destroy=extend_schema(tags=["Teacher Level"]),
)
class TeacherLevelViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    search_fields = ["level"]
    ordering_fields = ["level", "status"]
    ordering = ["level"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedAndActive()]
        return [IsPlatformSuperAdmin()]

    def get_queryset(self):
        qs = TeacherLevel.objects.all()

        # optional filters
        status_q = (self.request.query_params.get("status") or "").strip()
        if status_q:
            qs = qs.filter(status=status_q)

        include_deleted = (self.request.query_params.get("include_deleted") or "").strip().lower() in ("1", "true", "yes")
        if not include_deleted and "DELETED" in TeacherLevelStatus.__members__:
            qs = qs.exclude(status=TeacherLevelStatus.DELETED)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return TeacherLevelCreateSerializer
        if self.action in ("update", "partial_update"):
            return TeacherLevelUpdateSerializer
        return TeacherLevelReadSerializer

    def create(self, request, *args, **kwargs):
        s = TeacherLevelCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Teacher level created.", "data": TeacherLevelReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = TeacherLevelUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Teacher level updated.", "data": TeacherLevelReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = TeacherLevelUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Teacher level updated.", "data": TeacherLevelReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()

        # Soft delete if DELETED exists
        if "DELETED" in TeacherLevelStatus.__members__:
            obj.status = TeacherLevelStatus.DELETED
            obj.save(update_fields=["status"])
            return Response({"message": "Teacher level deleted."}, status=status.HTTP_204_NO_CONTENT)

        # otherwise: hard delete
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(tags=["Teacher Specialization"]),
    create=extend_schema(tags=["Teacher Specialization"], request=TeacherSpecializationWriteSerializer),
    retrieve=extend_schema(tags=["Teacher Specialization"]),
    update=extend_schema(tags=["Teacher Specialization"], request=TeacherSpecializationWriteSerializer),
    partial_update=extend_schema(tags=["Teacher Specialization"], request=TeacherSpecializationWriteSerializer),
    destroy=extend_schema(tags=["Teacher Specialization"]),
)
class TeacherSpecializationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    # Search by teacher name/phone/email, subject name/code (optional but useful)
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__phone",
        "user__email",
        "subjects__name",
        "subjects__code",
    ]
    ordering_fields = ["user__first_name", "user__last_name"]
    ordering = ["user__first_name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedAndActive()]
        return [IsPlatformSuperAdmin()]

    def get_queryset(self):
        qs = (
            TeacherSpecialization.objects
            .select_related("user", "teacher_level")
            .prefetch_related("subjects")
        )

        # Optional filters:
        user_id = (self.request.query_params.get("user") or "").strip()
        if user_id:
            qs = qs.filter(user_id=user_id)

        teacher_level_id = (self.request.query_params.get("teacher_level") or "").strip()
        if teacher_level_id:
            qs = qs.filter(teacher_level_id=teacher_level_id)

        subject_id = (self.request.query_params.get("subject") or "").strip()
        if subject_id:
            qs = qs.filter(subjects__id=subject_id)

        return qs.distinct()

    def get_serializer_class(self):
        # DRF's mixins call get_serializer_class; use write serializer for write actions
        if self.action in ("create", "update", "partial_update"):
            return TeacherSpecializationWriteSerializer
        return TeacherSpecializationReadSerializer

    def create(self, request, *args, **kwargs):
        s = TeacherSpecializationWriteSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Teacher specialization created.", "data": TeacherSpecializationReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = TeacherSpecializationWriteSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.update(obj, s.validated_data)
        return Response({"message": "Teacher specialization updated.", "data": TeacherSpecializationReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = TeacherSpecializationWriteSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        # treat partial by merging existing values
        data = dict(s.validated_data)

        # if user not provided, keep current
        data.setdefault("user", obj.user_id)

        # teacher_level: if missing, keep current (do nothing)
        if "teacher_level" not in data:
            pass

        # subjects: if missing, do nothing
        obj = s.update(obj, data)
        return Response({"message": "Teacher specialization updated.", "data": TeacherSpecializationReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)