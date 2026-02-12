from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.mixins import ListFilterMetaMixin
from common.pagination import MetaPageNumberPagination
from common.permissions import IsSchoolAdmin
from utils.get_school_id_by_token import get_school_for_user

from .models import EcaActivities, EcaActivityStatus
from .serializers import (
    EcaActivityCreateSerializer,
    EcaActivityReadSerializer,
    EcaActivityUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        operation_id="eca_activity_list",
        tags=["ECA Activities"],
        responses={200: EcaActivityReadSerializer(many=True)},
    ),
    create=extend_schema(
        operation_id="eca_activity_create",
        tags=["ECA Activities"],
        request=EcaActivityCreateSerializer,
        responses={201: EcaActivityReadSerializer},
    ),
    retrieve=extend_schema(
        operation_id="eca_activity_retrieve",
        tags=["ECA Activities"],
        responses={200: EcaActivityReadSerializer},
    ),
    update=extend_schema(
        operation_id="eca_activity_update",
        tags=["ECA Activities"],
        request=EcaActivityUpdateSerializer,
        responses={200: EcaActivityReadSerializer},
    ),
    partial_update=extend_schema(
        operation_id="eca_activity_partial_update",
        tags=["ECA Activities"],
        request=EcaActivityUpdateSerializer,
        responses={200: EcaActivityReadSerializer},
    ),
    destroy=extend_schema(
        operation_id="eca_activity_delete",
        tags=["ECA Activities"],
        responses={204: OpenApiResponse(description="Soft deleted (status=deleted).")},
    ),
)
class EcaActivityViewSet(
    ListFilterMetaMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    pagination_class = MetaPageNumberPagination

    # Search
    search_fields = ["name", "description"]
    searchable_fields = search_fields
    search_param_name = "search"

    # Ordering
    ordering_param_name = "ordering"
    ordering_fields = ["name", "status", "created_at", "updated_at"]
    public_sort_meta = {
        "name": "Name",
        "status": "Status",
        "created_at": "Created at",
        "updated_at": "Updated at",
    }
    sortable_fields = public_sort_meta

    # Filters
    public_filter_meta = {"status": "Status (active / inactive / archived / deleted / all)"}
    filterable_fields = public_filter_meta

    def _status_filter(self) -> str:
        return (self.request.query_params.get("status") or "active").lower().strip()

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        qs = EcaActivities.objects.filter(school=school).select_related("school", "fees")

        status_filter = self._status_filter()
        if status_filter == "active":
            qs = qs.filter(status=EcaActivityStatus.active)
        elif status_filter == "inactive":
            qs = qs.filter(status=EcaActivityStatus.inactive)
        elif status_filter == "archived":
            qs = qs.filter(status=EcaActivityStatus.archived)
        elif status_filter == "deleted":
            qs = qs.filter(status=EcaActivityStatus.deleted)
        elif status_filter == "all":
            pass
        else:
            raise ValidationError({"status": ["Invalid value. Use: active, inactive, archived, deleted, all."]})

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return EcaActivityCreateSerializer
        if self.action in ("update", "partial_update"):
            return EcaActivityUpdateSerializer
        return EcaActivityReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = EcaActivityCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "ECA activity created successfully.", "data": EcaActivityReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status == EcaActivityStatus.deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        obj.status = EcaActivityStatus.deleted
        obj.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["patch"], url_path="activate")
    def activate(self, request, pk=None):
        obj = self.get_object()
        obj.status = EcaActivityStatus.active
        obj.save(update_fields=["status", "updated_at"])
        return Response(
            {"message": "Activated.", "data": EcaActivityReadSerializer(obj).data},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["patch"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        obj.status = EcaActivityStatus.inactive
        obj.save(update_fields=["status", "updated_at"])
        return Response(
            {"message": "Deactivated.", "data": EcaActivityReadSerializer(obj).data},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["patch"], url_path="archive")
    def archive(self, request, pk=None):
        obj = self.get_object()
        obj.status = EcaActivityStatus.archived
        obj.save(update_fields=["status", "updated_at"])
        return Response(
            {"message": "Archived.", "data": EcaActivityReadSerializer(obj).data},
            status=status.HTTP_200_OK,
        )
