from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response

from accounts.models import User
from common.constants import UserStatus
from common.mixins import ListFilterMetaMixin
from common.pagination import MetaPageNumberPagination
from common.permissions import IsSchoolAdmin, IsAuthenticatedAndActive
from utils.get_school_id_by_token import get_school_for_user

from .staff_serializers import (
    ALLOWED_STAFF_ROLES,
    StaffCreateUpdateSerializer,
    StaffUpdateSerializer,   # <- create this (below note)
)
from .staff_serializers_read import StaffUserReadSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        operation_id="staff_user_list",
        tags=["Staff"],
        responses={200: StaffUserReadSerializer(many=True)},
    ),
    create=extend_schema(
        operation_id="staff_user_create",
        tags=["Staff"],
        request=StaffCreateUpdateSerializer,
        responses={201: StaffUserReadSerializer},
    ),
    retrieve=extend_schema(
        operation_id="staff_user_retrieve",
        tags=["Staff"],
        responses={200: StaffUserReadSerializer},
    ),
    update=extend_schema(
        operation_id="staff_user_update",
        tags=["Staff"],
        request=StaffUpdateSerializer,
        responses={200: StaffUserReadSerializer},
    ),
    partial_update=extend_schema(
        operation_id="staff_user_partial_update",
        tags=["Staff"],
        request=StaffUpdateSerializer,
        responses={200: StaffUserReadSerializer},
    ),
    destroy=extend_schema(
        operation_id="staff_user_delete",
        tags=["Staff"],
        responses={204: OpenApiResponse(description="Deleted.")},
    ),
)
class StaffUserViewSet(
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
    lookup_field = "pk"

    # search configuration
    search_fields = ["first_name", "middle_name", "last_name", "phone", "email", "username"]
    searchable_fields = search_fields
    search_param_name = "search"
    filter_backends = [SearchFilter, OrderingFilter]

    # ordering configuration
    ordering_param_name = "ordering"
    ordering_fields = ["first_name", "last_name", "phone", "email", "role", "status", "date_joined"]
    public_sort_meta = {
        "first_name": "First name",
        "last_name": "Last name",
        "phone": "Phone",
        "email": "Email",
        "role": "Role",
        "status": "Status",
        "date_joined": "Created at",
    }
    sortable_fields = public_sort_meta

    # filter configuration
    public_filter_meta = {
        "status": "Status (active / inactive / all)",
        "role": "Role (teacher / coordinator / etc.)",
    }
    filterable_fields = public_filter_meta

    def _status_filter(self) -> str:
        return (self.request.query_params.get("status") or "all").lower().strip()

    def _role_filter(self) -> str | None:
        v = (self.request.query_params.get("role") or "").strip()
        return v or None

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        qs = (
            User.objects.filter(
                is_deleted=False,
                role__in=list(ALLOWED_STAFF_ROLES),
                profile__school=school,
            )
            .select_related("profile")
            .prefetch_related("profile__addresses", "profile__documents")
        )

        # status filter
        status_filter = self._status_filter()
        if status_filter == "active":
            qs = qs.filter(status=UserStatus.ACTIVE)
        elif status_filter == "inactive":
            qs = qs.filter(status=UserStatus.INACTIVE)
        elif status_filter == "all":
            pass
        else:
            raise ValidationError({"status": ["Invalid value. Use: active, inactive, all."]})

        # role filter (optional)
        role_filter = self._role_filter()
        if role_filter:
            role_filter = role_filter.lower().replace("-", "_")
            if role_filter not in [r for r in ALLOWED_STAFF_ROLES]:
                raise ValidationError({"role": ["Invalid role filter."]})
            qs = qs.filter(role=role_filter)

        return qs.order_by("-date_joined")

    def get_serializer_class(self):
        if self.action == "create":
            return StaffCreateUpdateSerializer
        if self.action in ("update", "partial_update"):
            return StaffUpdateSerializer
        return StaffUserReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = StaffCreateUpdateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()  # serializer.create returns a dict? better to return User instance; see note below.

        # If your create() currently returns dict, change it to return user instance.
        # Here we handle both:
        if isinstance(obj, User):
            return Response(
                {"message": "Staff user created successfully.", "data": StaffUserReadSerializer(obj).data},
                status=status.HTTP_201_CREATED,
            )

        # fallback: obj is dict
        return Response(
            {"message": "Staff user created successfully.", "data": obj},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        user: User = self.get_object()

        if user.status != UserStatus.ACTIVE:
            raise ValidationError({"detail": "Only ACTIVE staff users can be updated."})

        serializer = StaffUpdateSerializer(
            instance=user,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {"message": "Staff user updated successfully.", "data": StaffUserReadSerializer(user).data},
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        user: User = self.get_object()

        if user.status != UserStatus.ACTIVE:
            raise ValidationError({"detail": "Only ACTIVE staff users can be updated."})

        serializer = StaffUpdateSerializer(
            instance=user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {"message": "Staff user updated successfully.", "data": StaffUserReadSerializer(user).data},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        user: User = self.get_object()

        if user.status != UserStatus.ACTIVE:
            raise ValidationError({"detail": "Only ACTIVE staff users can be deleted."})

        user.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
