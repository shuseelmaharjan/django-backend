from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from common.mixins import ListFilterMetaMixin
from common.pagination import MetaPageNumberPagination
from common.permissions import IsSchoolAdmin, IsAuthenticatedAndActive
from utils.get_school_id_by_token import get_school_for_user

from .models import Billing
from .serializers import (
    BillingCreateSerializer,
    BillingReadSerializer,
    BillingUpdateSerializer,
    BillingUndoSerializer,
)


@extend_schema_view(
    list=extend_schema(
        operation_id="billing_list",
        tags=["Billing"],
        responses={200: BillingReadSerializer(many=True)},
    ),
    create=extend_schema(
        operation_id="billing_create",
        tags=["Billing"],
        request=BillingCreateSerializer,
        responses={201: BillingReadSerializer},
    ),
    retrieve=extend_schema(
        operation_id="billing_retrieve",
        tags=["Billing"],
        responses={200: BillingReadSerializer},
    ),
    update=extend_schema(
        operation_id="billing_update",
        tags=["Billing"],
        request=BillingUpdateSerializer,
        responses={200: BillingReadSerializer},
    ),
    partial_update=extend_schema(
        operation_id="billing_partial_update",
        tags=["Billing"],
        request=BillingUpdateSerializer,
        responses={200: BillingReadSerializer},
    ),
    destroy=extend_schema(
        operation_id="billing_delete",
        tags=["Billing"],
        responses={204: OpenApiResponse(description="Hard deleted.")},
    ),
)
class BillingViewSet(
    ListFilterMetaMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolAdmin]
    pagination_class = MetaPageNumberPagination

    # Search
    search_fields = ["receipt_number", "inwords", "description"]
    searchable_fields = search_fields
    search_param_name = "search"

    # Ordering
    ordering_param_name = "ordering"
    ordering_fields = ["created_at", "amount", "status"]
    public_sort_meta = {
        "created_at": "Created at",
        "amount": "Amount",
        "status": "Status",
    }
    sortable_fields = public_sort_meta

    # Filters
    public_filter_meta = {"status": "Status (pending / paid / overdue / all)"}
    filterable_fields = public_filter_meta

    def _status_filter(self) -> str:
        return (self.request.query_params.get("status") or "all").lower().strip()

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        # assumes User has school_id, and Billing.student points to that User
        qs = Billing.objects.filter(student__school_id=school.id).select_related("student", "received_by")

        status_filter = self._status_filter()
        if status_filter == "all":
            return qs
        if status_filter in ("pending", "paid", "overdue"):
            return qs.filter(status=status_filter)

        raise ValidationError({"status": ["Invalid value. Use: pending, paid, overdue, all."]})

    def get_serializer_class(self):
        if self.action == "create":
            return BillingCreateSerializer
        if self.action in ("update", "partial_update"):
            return BillingUpdateSerializer
        return BillingReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = BillingCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Billing created successfully.", "data": BillingReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = BillingUpdateSerializer(
            data=request.data,
            context={"request": request, "instance": instance},
            partial=False,
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.update(instance, serializer.validated_data)
        return Response(
            {"message": "Billing updated successfully.", "data": BillingReadSerializer(obj).data},
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = BillingUpdateSerializer(
            data=request.data,
            context={"request": request, "instance": instance},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.update(instance, serializer.validated_data)
        return Response(
            {"message": "Billing updated successfully.", "data": BillingReadSerializer(obj).data},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        operation_id="billing_undo",
        tags=["Billing"],
        request=BillingUndoSerializer,
        responses={200: BillingReadSerializer, 204: OpenApiResponse(description="Voided (deleted).")},
    )
    @action(detail=True, methods=["post"], url_path="undo")
    def undo(self, request, pk=None):
        """
        Undo supports:
          - mode=unpay: paid -> pending, clears payment_method & received_by
          - mode=void: hard delete the billing
        """
        obj = self.get_object()
        s = BillingUndoSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        mode = s.validated_data["mode"]

        if mode == "unpay":
            if obj.status != "paid":
                raise ValidationError({"mode": ["Only paid billings can be unpaid."]})

            obj.status = "pending"
            obj.payment_method = None
            obj.received_by = None
            obj.save(update_fields=["status", "payment_method", "received_by"])
            return Response(
                {"message": "Payment undone (set back to pending).", "data": BillingReadSerializer(obj).data},
                status=status.HTTP_200_OK,
            )

        # mode == "void"
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
