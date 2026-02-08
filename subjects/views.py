# subjects/views.py
from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets, filters
from rest_framework.response import Response

from common.permissions import IsPlatformSuperAdmin, IsAuthenticatedAndActive
from subjects.models import Subject, SubjectStatus
from subjects.serializers import (
    SubjectCreateSerializer,
    SubjectUpdateSerializer,
    SubjectReadSerializer,
)
from rest_framework.decorators import action
from subjects.serializers import SubjectReorderSerializer
from subjects.serializers import SubjectStatusToggleSerializer


@extend_schema_view(
    list=extend_schema(tags=["Subject"]),
    create=extend_schema(tags=["Subject"], request=SubjectCreateSerializer),
    retrieve=extend_schema(tags=["Subject"]),
    update=extend_schema(tags=["Subject"], request=SubjectUpdateSerializer),
    partial_update=extend_schema(tags=["Subject"], request=SubjectUpdateSerializer),
    destroy=extend_schema(tags=["Subject"]),
    reorder=extend_schema(tags=["Subject"], request=SubjectReorderSerializer),
)

class SubjectViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "sort_order", "created_at", "updated_at", "status"]
    ordering = ["sort_order", "name"]

    def get_permissions(self):
        """
        - GET list/retrieve => any authenticated & active user
        - POST/PUT/PATCH/DELETE => only platform super admin
        """
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedAndActive()]
        return [IsPlatformSuperAdmin()]

    def get_queryset(self):
        qs = Subject.objects.all()

        status_q = (self.request.query_params.get("status") or "").strip()
        if status_q:
            qs = qs.filter(status=status_q)

        include_deleted = (
            (self.request.query_params.get("include_deleted") or "")
            .strip()
            .lower()
            in ("1", "true", "yes")
        )
        if not include_deleted:
            qs = qs.exclude(status=SubjectStatus.DELETED)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return SubjectCreateSerializer
        if self.action in ("update", "partial_update"):
            return SubjectUpdateSerializer
        return SubjectReadSerializer

    def create(self, request, *args, **kwargs):
        s = SubjectCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Subject created.", "data": SubjectReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = SubjectUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Subject updated.", "data": SubjectReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = SubjectUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Subject updated.", "data": SubjectReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.status = SubjectStatus.DELETED
        obj.save(update_fields=["status", "updated_at"])
        return Response({"message": "Subject deleted."}, status=status.HTTP_204_NO_CONTENT)

    @extend_schema(tags=["Subject"], request=SubjectReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        """
        Drag & drop sorting endpoint
        """
        s = SubjectReorderSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response({"message": "Subjects reordered.", "data": result}, status=status.HTTP_200_OK)

    @extend_schema(tags=["Subject"], request=SubjectStatusToggleSerializer, responses=SubjectReadSerializer)
    @action(detail=True, methods=["post"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        obj = self.get_object()
        s = SubjectStatusToggleSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save(subject=obj)
        return Response({"message": "Subject status updated.", "data": SubjectReadSerializer(obj).data},
                        status=status.HTTP_200_OK)
