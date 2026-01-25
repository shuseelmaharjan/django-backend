# onboarding/views.py
from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.pagination import MetaPageNumberPagination
from common.mixins import ListFilterMetaMixin

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
)

from .serializers import (
    AdminOnboardingCreateSerializer,
    AdminOnboardingReadSerializer,
    AdminOnboardingUpdateSerializer,
    AdminOnboardingListSerializer,
)
from .services import (
    fetch_onboarding_bundle_by_user,
    update_onboarding_bundle_by_user,
    delete_onboarding_bundle_by_user,
)


@extend_schema_view(
    list=extend_schema(
        operation_id="admin_onboarding_list",
        tags=["Onboarding"],
        parameters=[
            OpenApiParameter(name="search", required=False, type=str, description="Search by phone/email/name/username"),
            OpenApiParameter(name="ordering", required=False, type=str, description="Order by: date_joined, first_name, last_name, email (add - for desc)"),
            OpenApiParameter(name="page", required=False, type=int),
            OpenApiParameter(name="page_size", required=False, type=int),
        ],
        responses={200: AdminOnboardingListSerializer},
        examples=[OpenApiExample(name="List admin bundles", value={"results": []}, response_only=True)],
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
        responses={200: AdminOnboardingReadSerializer, 404: OpenApiResponse(description="Not found.")},
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

    # Filter configuration for the mixin
    public_filter_meta = {}
    public_sort_meta = {
        "date_joined": "Date joined",
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
    }

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
        return Response(result, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        from accounts.models import User
        from common.constants import UserRole
        from django.db.models import Q

        queryset = (
            User.objects
            .filter(role=UserRole.ADMIN)
            .exclude(is_superuser=True)
        )

        # Handle search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(username__icontains=search)
            )

        # Handle ordering
        ordering = self.request.query_params.get('ordering', '-date_joined')
        queryset = queryset.order_by(ordering)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            results = []
            for user in page:
                bundle = fetch_onboarding_bundle_by_user(user_id=str(user.id), request=request, allow_incomplete=True)
                results.append(bundle)
            return self.get_paginated_response(results)

        # Fallback if pagination is not configured
        results = []
        for user in queryset:
            bundle = fetch_onboarding_bundle_by_user(user_id=str(user.id), request=request, allow_incomplete=True)
            results.append(bundle)
        return Response({"results": results}, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        user_id = kwargs["pk"]
        bundle = fetch_onboarding_bundle_by_user(user_id=user_id, request=request, allow_incomplete=True)
        return Response(bundle, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        user_id = kwargs["pk"]
        serializer = AdminOnboardingUpdateSerializer(data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)

        bundle = update_onboarding_bundle_by_user(
            user_id=user_id,
            validated_data=serializer.validated_data,
            partial=False,
        )
        return Response(bundle, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        user_id = kwargs["pk"]
        serializer = AdminOnboardingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        bundle = update_onboarding_bundle_by_user(
            user_id=user_id,
            validated_data=serializer.validated_data,
            partial=True,
        )
        return Response(bundle, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        user_id = kwargs["pk"]
        delete_onboarding_bundle_by_user(user_id=user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
