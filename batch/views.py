from __future__ import annotations

import logging
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AcademicBatch
from .serializers import (
    AcademicBatchCreateSerializer,
    AcademicBatchReadSerializer,
    AcademicBatchUpdateSerializer,
)
from common.permissions import IsSchoolAdmin
from common.pagination import MetaPageNumberPagination
from common.mixins import ListFilterMetaMixin
from utils.get_school_id_by_token import get_school_for_user
from rest_framework.filters import SearchFilter, OrderingFilter

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        operation_id="batch_list",
        tags=["Batch"],
        responses={200: AcademicBatchReadSerializer(many=True)},
    ),
    create=extend_schema(
        operation_id="batch_create",
        tags=["Batch"],
        request=AcademicBatchCreateSerializer,
        responses={201: AcademicBatchReadSerializer},
    ),
    retrieve=extend_schema(
        operation_id="batch_retrieve",
        tags=["Batch"],
        responses={200: AcademicBatchReadSerializer},
    ),
    update=extend_schema(
        operation_id="batch_update",
        tags=["Batch"],
        request=AcademicBatchUpdateSerializer,
        responses={200: AcademicBatchReadSerializer},
    ),
    partial_update=extend_schema(
        operation_id="batch_partial_update",
        tags=["Batch"],
        request=AcademicBatchUpdateSerializer,
        responses={200: AcademicBatchReadSerializer},
    ),
    destroy=extend_schema(
        operation_id="batch_delete",
        tags=["Batch"],
        responses={
            204: OpenApiResponse(description="Deleted."),
            400: OpenApiResponse(description="Cannot delete if already started."),
        },
    ),
)
class AcademicBatchViewSet(
    ListFilterMetaMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    lookup_field = "pk"
    pagination_class = MetaPageNumberPagination
    #search configuration
    search_fields = ['name']  # example searchable field
    searchable_fields = search_fields
    search_param_name = "search"

    # ordering configuration
    ordering_param_name = "ordering"
    ordering_fields = ["name", "start_date_ad", "end_date_ad", "created_at"]
    public_sort_meta = {
        "name": "Name",
        "start_date_ad": "Start date",
        "end_date_ad": "End date",
        "created_at": "Created at",
    }
    sortable_fields = public_sort_meta

    # filter configuration
    public_filter_meta = {
        "status": "Status (active / inactive / all)",
    }
    filterable_fields = public_filter_meta

    def _status_filter(self) -> str:
        return (self.request.query_params.get("status") or "all").lower().strip()

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        qs = AcademicBatch.objects.filter(school=school)

        status_filter = self._status_filter()
        if status_filter == "active":
            qs = qs.filter(is_active=True)
        elif status_filter == "inactive":
            qs = qs.filter(is_active=False)
        elif status_filter == "all":
            pass
        else:
            raise ValidationError({"status": ["Invalid value. Use: active, inactive, all."]})

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return AcademicBatchCreateSerializer
        if self.action in ("update", "partial_update"):
            return AcademicBatchUpdateSerializer
        return AcademicBatchReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = AcademicBatchCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Batch created successfully.", "data": AcademicBatchReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["patch"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        if not obj.is_active:
            return Response(
                {"message": "Batch is already inactive.", "data": AcademicBatchReadSerializer(obj).data},
                status=status.HTTP_200_OK,
            )
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        return Response(
            {"message": "Batch deactivated successfully.", "data": AcademicBatchReadSerializer(obj).data},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        today = timezone.localdate()

        logger.warning("DELETE batch=%s start_date_ad=%s today=%s created_at=%s",
                       obj.id, obj.start_date_ad, today, obj.created_at)

        if obj.start_date_ad <= today:
            raise ValidationError({"detail": "Cannot delete a batch that has already started."})

        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
