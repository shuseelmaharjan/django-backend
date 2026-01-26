# onboarding/views.py
from __future__ import annotations

import logging

from django.db.models import Exists, OuterRef, Q
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from common.constants import UserRole, UserStatus
from common.mixins import ListFilterMetaMixin
from common.pagination import MetaPageNumberPagination
from schools.models import School

from .serializers import (
    AdminOnboardingCreateSerializer,
    AdminOnboardingListSerializer,
    AdminOnboardingReadSerializer,
    AdminOnboardingUpdateSerializer,
)
from .services import (
    delete_onboarding_bundle_by_user,
    fetch_onboarding_bundle_by_user,
    update_onboarding_bundle_by_user,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        operation_id="admin_onboarding_list",
        tags=["Onboarding"],
        parameters=[
            OpenApiParameter(
                name="search",
                required=False,
                type=str,
                description="Search by phone/email/name/username",
            ),
            OpenApiParameter(
                name="ordering",
                required=False,
                type=str,
                description="Order by: date_joined, first_name, last_name, email (add - for desc)",
            ),
            OpenApiParameter(name="page", required=False, type=int),
            OpenApiParameter(name="page_size", required=False, type=int),
            OpenApiParameter(
                name="status_filter",
                required=False,
                type=str,
                description="Filter by status: active | deactive | all (default: active)",
            ),
        ],
        responses={200: AdminOnboardingListSerializer},
        examples=[
            OpenApiExample(name="List admin bundles", value={"results": []}, response_only=True)
        ],
    ),
    create=extend_schema(
        operation_id="admin_onboarding_create",
        tags=["Onboarding"],
        request=AdminOnboardingCreateSerializer,
        responses={
            201: OpenApiResponse(description="Created bundle (ids)."),
            400: OpenApiResponse(description="Validation error (nested)."),
        },
    ),
    retrieve=extend_schema(
        operation_id="admin_onboarding_retrieve",
        tags=["Onboarding"],
        responses={
            200: AdminOnboardingReadSerializer,
            404: OpenApiResponse(description="Not found."),
        },
    ),
    update=extend_schema(
        operation_id="admin_onboarding_update",
        tags=["Onboarding"],
        request=AdminOnboardingUpdateSerializer,
        responses={
            200: AdminOnboardingReadSerializer,
            400: OpenApiResponse(description="Validation error (nested)."),
            404: OpenApiResponse(description="Not found."),
        },
    ),
    partial_update=extend_schema(
        operation_id="admin_onboarding_partial_update",
        tags=["Onboarding"],
        request=AdminOnboardingUpdateSerializer,
        responses={
            200: AdminOnboardingReadSerializer,
            400: OpenApiResponse(description="Validation error (nested)."),
            404: OpenApiResponse(description="Not found."),
        },
    ),
    destroy=extend_schema(
        operation_id="admin_onboarding_delete",
        tags=["Onboarding"],
        responses={
            204: OpenApiResponse(description="Deactivated school + soft-deleted admin user."),
            404: OpenApiResponse(description="Not found."),
        },
    ),
)
class AdminOnboardingViewSet(
    ListFilterMetaMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    URL {pk} is ADMIN USER ID (UUID)
    /api/onboarding/admin/{user_id}/
    """
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"
    pagination_class = MetaPageNumberPagination

    # Search configuration
    search_fields = ["first_name", "last_name", "email", "phone", "username"]

    # Sort configuration
    public_sort_meta = {
        "date_joined": "Date joined",
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
    }

    # Filter meta
    public_filter_meta = {
        "status_filter": "Status (active / deactive / all)",
    }

    # ---- MetaPageNumberPagination expects these ----
    filterable_fields = public_filter_meta
    sortable_fields = public_sort_meta
    searchable_fields = search_fields
    ordering_param_name = "ordering"
    search_param_name = "search"

    def get_serializer_class(self):
        if self.action == "create":
            return AdminOnboardingCreateSerializer
        if self.action in ("update", "partial_update"):
            return AdminOnboardingUpdateSerializer
        if self.action == "list":
            return AdminOnboardingListSerializer
        return AdminOnboardingReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = AdminOnboardingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {"message": "Admin onboarding created successfully.", "data": result},
            status=status.HTTP_201_CREATED,
        )

    def _status_filter(self) -> str:
        return (self.request.query_params.get("status_filter") or "active").lower().strip()

    def _validated_ordering(self, queryset):
        """
        Prevent 500s caused by invalid ordering fields.
        Only allow fields listed in public_sort_meta.
        """
        ordering = self.request.query_params.get(self.ordering_param_name, "-date_joined")
        ordering = (ordering or "-date_joined").strip()

        allowed = set(self.public_sort_meta.keys())
        field = ordering.lstrip("-")

        if field not in allowed:
            raise ValidationError(
                {
                    self.ordering_param_name: [
                        f"Invalid ordering field. Allowed: {', '.join(sorted(allowed))}"
                    ]
                }
            )
        return queryset.order_by(ordering)

    def get_queryset(self):
        status_filter = self._status_filter()

        # Subquery: does this user own an active school?
        active_school_exists = School.objects.filter(owner=OuterRef("pk"), is_active=True)

        # Use all_objects only when "all" is requested
        base_manager = User.all_objects if status_filter == "all" else User.objects

        queryset = (
            base_manager.filter(role=UserRole.ADMIN)
            .exclude(is_superuser=True)
            .annotate(has_active_school=Exists(active_school_exists))
        )

        if status_filter == "active":
            queryset = queryset.filter(status=UserStatus.ACTIVE, has_active_school=True)

        elif status_filter == "deactive":
            deactive_statuses = [UserStatus.DELETED, UserStatus.INACTIVE]
            queryset = queryset.filter(status__in=deactive_statuses, has_active_school=False)

        elif status_filter == "all":
            pass

        else:
            raise ValidationError({"status_filter": ["Invalid value. Use: active, deactive, all."]})

        # Search
        search = (self.request.query_params.get(self.search_param_name) or "").strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(username__icontains=search)
            )

        # Ordering (validated)
        return self._validated_ordering(queryset)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        status_filter = self._status_filter()
        include_deleted = status_filter == "all"

        page = self.paginate_queryset(queryset)
        users = page if page is not None else queryset

        results = []
        for user in users:
            try:
                bundle = fetch_onboarding_bundle_by_user(
                    user_id=str(user.id),
                    request=request,
                    allow_incomplete=True,
                    include_deleted=include_deleted,
                )
                results.append(bundle)
            except Exception as e:
                # IMPORTANT: this will show you the real reason in logs
                logger.exception("Admin onboarding list bundle failed for user_id=%s", user.id)

                # Return a safe error entry instead of crashing the endpoint
                results.append(
                    {
                        "user_id": str(user.id),
                        "serial": None,  # pagination will overwrite serial if dict
                        "error": "Failed to build onboarding bundle for this user.",
                        "error_detail": str(e),
                    }
                )

        if page is not None:
            return self.get_paginated_response(results)

        return Response({"results": results}, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        user_id = kwargs["pk"]
        status_filter = self._status_filter()
        include_deleted = status_filter == "all"

        bundle = fetch_onboarding_bundle_by_user(
            user_id=user_id,
            request=request,
            allow_incomplete=True,
            include_deleted=include_deleted,
        )
        return Response(bundle, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        user_id = kwargs["pk"]
        serializer = AdminOnboardingUpdateSerializer(data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)

        bundle = update_onboarding_bundle_by_user(
            user_id=user_id,
            request=request,
            validated_data=serializer.validated_data,
            partial=False,
        )

        return Response(
            {"message": "Onboarding updated successfully.", "data": bundle},
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        user_id = kwargs["pk"]
        serializer = AdminOnboardingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        bundle = update_onboarding_bundle_by_user(
            user_id=user_id,
            request=request,
            validated_data=serializer.validated_data,
            partial=True,
        )

        return Response(
            {"message": "Onboarding partially updated successfully.", "data": bundle},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        user_id = kwargs["pk"]
        delete_onboarding_bundle_by_user(user_id=user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
