from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response

from accounts.models import User
from common.constants import UserRole, UserStatus
from common.mixins import ListFilterMetaMixin
from common.pagination import MetaPageNumberPagination
from common.permissions import IsAuthenticatedAndActive, CanEnrollStudents
from utils.get_school_id_by_token import get_school_for_user

from .student_serializers import StudentCreateUpdateSerializer, StudentUpdateSerializer
from .student_serializers_read import StudentUserReadSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        operation_id="student_user_list",
        tags=["Students"],
        responses={200: StudentUserReadSerializer(many=True)},
    ),
    create=extend_schema(
        operation_id="student_user_create",
        tags=["Students"],
        request=StudentCreateUpdateSerializer,
        responses={201: StudentUserReadSerializer},
    ),
    retrieve=extend_schema(
        operation_id="student_user_retrieve",
        tags=["Students"],
        responses={200: StudentUserReadSerializer},
    ),
    update=extend_schema(
        operation_id="student_user_update",
        tags=["Students"],
        request=StudentUpdateSerializer,
        responses={200: StudentUserReadSerializer},
    ),
    partial_update=extend_schema(
        operation_id="student_user_partial_update",
        tags=["Students"],
        request=StudentUpdateSerializer,
        responses={200: StudentUserReadSerializer},
    ),
    destroy=extend_schema(
        operation_id="student_user_delete",
        tags=["Students"],
        responses={204: OpenApiResponse(description="Deleted.")},
    ),
)
class StudentUserViewSet(
    ListFilterMetaMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, CanEnrollStudents]
    pagination_class = MetaPageNumberPagination
    lookup_field = "pk"

    search_fields = ["first_name", "middle_name", "last_name", "phone", "email", "username"]
    searchable_fields = search_fields
    search_param_name = "search"
    filter_backends = [SearchFilter, OrderingFilter]

    ordering_param_name = "ordering"
    ordering_fields = ["first_name", "last_name", "phone", "email", "status", "date_joined"]
    public_sort_meta = {
        "first_name": "First name",
        "last_name": "Last name",
        "phone": "Phone",
        "email": "Email",
        "status": "Status",
        "date_joined": "Created at",
    }
    sortable_fields = public_sort_meta

    public_filter_meta = {
        "status": "Status (active / inactive / all)",
    }
    filterable_fields = public_filter_meta

    def _status_filter(self) -> str:
        return (self.request.query_params.get("status") or "all").lower().strip()

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        qs = (
            User.objects.filter(
                is_deleted=False,
                role=UserRole.STUDENT,
                profile__school=school,
            )
            .select_related("profile")
            .prefetch_related("profile__addresses", "profile__documents", "profile__student_other_info")
        )

        status_filter = self._status_filter()
        if status_filter == "active":
            qs = qs.filter(status=UserStatus.ACTIVE)
        elif status_filter == "inactive":
            qs = qs.filter(status=UserStatus.INACTIVE)
        elif status_filter == "all":
            pass
        elif status_filter == "draft":
            qs = qs.filter(status=UserStatus.DRAFT)
        else:
            raise ValidationError({"status": ["Invalid value. Use: active, inactive, all."]})

        return qs.order_by("-date_joined")

    def get_serializer_class(self):
        if self.action == "create":
            return StudentCreateUpdateSerializer
        if self.action in ("update", "partial_update"):
            return StudentUpdateSerializer
        return StudentUserReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = StudentCreateUpdateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {"message": "Student enrolled successfully.", "data": StudentUserReadSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        user: User = self.get_object()
        if user.status != UserStatus.ACTIVE:
            raise ValidationError({"detail": "Only ACTIVE students can be updated."})

        serializer = StudentUpdateSerializer(instance=user, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {"message": "Student updated successfully.", "data": StudentUserReadSerializer(user).data},
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        user: User = self.get_object()
        if user.status != UserStatus.ACTIVE:
            raise ValidationError({"detail": "Only ACTIVE students can be updated."})

        serializer = StudentUpdateSerializer(instance=user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {"message": "Student updated successfully.", "data": StudentUserReadSerializer(user).data},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        user: User = self.get_object()
        if user.status != UserStatus.ACTIVE:
            raise ValidationError({"detail": "Only ACTIVE students can be deleted."})

        user.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
