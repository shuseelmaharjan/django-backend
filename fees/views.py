from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.response import Response

from common.mixins import ListFilterMetaMixin
from common.pagination import MetaPageNumberPagination
from common.permissions import IsPlatformSuperAdmin, IsSchoolAdmin, IsAuthenticatedAndActive
from .models import FeeHead, FeeStructure
from .serializers import FeeHeadSerializer, FeeStructureSerializer
from utils.get_school_id_by_token import get_school_for_user
from rest_framework.decorators import action


TRUE_VALUES = {"true", "1", "yes"}
FALSE_VALUES = {"false", "0", "no"}


@extend_schema_view(
    list=extend_schema(tags=["FeeHead"]),
    create=extend_schema(tags=["FeeHead"], request=FeeHeadSerializer),
    retrieve=extend_schema(tags=["FeeHead"]),
    update=extend_schema(tags=["FeeHead"], request=FeeHeadSerializer),
    partial_update=extend_schema(tags=["FeeHead"], request=FeeHeadSerializer),
    destroy=extend_schema(tags=["FeeHead"]),
)
class FeeHeadViewSet(
    ListFilterMetaMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FeeHeadSerializer
    queryset = FeeHead.objects.all().order_by("name")
    pagination_class = MetaPageNumberPagination

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "group", "is_active", "created_at", "updated_at"]
    ordering = ["name"]

    # used by ListFilterMetaMixin -> MetaPageNumberPagination.meta
    public_filter_meta = {
        "is_active": {
            "type": "boolean",
            "label": "Active",
            "choices": [
                {"label": "Active", "value": "true"},
                {"label": "Inactive", "value": "false"},
            ],
        },
        "group": {
            "type": "string",
            "label": "Group",
        },
    }

    public_sort_meta = {
        "name": {"label": "Name"},
        "code": {"label": "Code"},
        "group": {"label": "Group"},
        "is_active": {"label": "Active"},
        "created_at": {"label": "Created At"},
        "updated_at": {"label": "Updated At"},
    }

    def get_permissions(self):
        if self.action in ("list", "retrieve", "active_for_school"):
            return [IsAuthenticatedAndActive()]
        return [IsPlatformSuperAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        is_active = params.get("is_active")
        if is_active is not None:
            val = is_active.strip().lower()
            if val in TRUE_VALUES:
                qs = qs.filter(is_active=True)
            elif val in FALSE_VALUES:
                qs = qs.filter(is_active=False)

        group = params.get("group")
        if group:
            qs = qs.filter(group=group)

        return qs

    @action(
        detail=False,
        methods=["get"],
        url_path="active-for-school",
        permission_classes=[IsAuthenticatedAndActive],
    )
    def active_for_school(self, request):
        # This ensures token->school resolution works and blocks users without school
        _school = get_school_for_user(request.user)

        qs = FeeHead.objects.filter(is_active=True).order_by("name")
        data = FeeHeadSerializer(qs, many=True).data
        return Response({"message": "Active fee heads.", "data": data}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Fee head created.", "data": self.get_serializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = self.get_serializer(instance=obj, data=request.data, partial=False, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Fee head updated.", "data": self.get_serializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = self.get_serializer(instance=obj, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Fee head updated.", "data": self.get_serializer(obj).data})

    # Keep hard delete, or change to soft delete here if desired
    # def destroy(self, request, *args, **kwargs):
    #     obj = self.get_object()
    #     obj.is_active = False
    #     obj.save(update_fields=["is_active"])
    #     return Response({"message": "Fee head deactivated."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["FeeStructure"]),
    create=extend_schema(tags=["FeeStructure"], request=FeeStructureSerializer),
    retrieve=extend_schema(tags=["FeeStructure"]),
    update=extend_schema(tags=["FeeStructure"], request=FeeStructureSerializer),
    partial_update=extend_schema(tags=["FeeStructure"], request=FeeStructureSerializer),
    destroy=extend_schema(tags=["FeeStructure"]),
)
class FeeStructureViewSet(
    ListFilterMetaMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FeeStructureSerializer
    pagination_class = MetaPageNumberPagination

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "fee_head__name",
        "fee_head__code",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "amount",
        "period",
        "status",
        "scope",
    ]
    ordering = ["-created_at"]

    # Meta info for your frontend (ListFilterMetaMixin)
    public_filter_meta = {
        "status": {"type": "string", "label": "Status"},
        "scope": {"type": "string", "label": "Scope"},
        "period": {"type": "string", "label": "Period"},
        "fee_head": {"type": "uuid", "label": "Fee head id"},
        "batch": {"type": "int", "label": "Batch id"},
        "academic_class": {"type": "uuid", "label": "Class id"},
    }

    public_sort_meta = {
        "created_at": {"label": "Created At"},
        "updated_at": {"label": "Updated At"},
        "amount": {"label": "Amount"},
        "period": {"label": "Period"},
        "status": {"label": "Status"},
        "scope": {"label": "Scope"},
    }

    def get_permissions(self):
        # read allowed for authenticated users of that school
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedAndActive()]
        # write only for school admin
        return [IsAuthenticatedAndActive(), IsSchoolAdmin()]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        qs = (
            FeeStructure.objects
            .select_related("fee_head", "school", "batch", "academic_class")
            .filter(school=school)
        )

        p = self.request.query_params

        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("scope"):
            qs = qs.filter(scope=p["scope"])
        if p.get("period"):
            qs = qs.filter(period=p["period"])
        if p.get("fee_head"):
            qs = qs.filter(fee_head_id=p["fee_head"])
        if p.get("batch"):
            qs = qs.filter(batch_id=p["batch"])
        if p.get("academic_class"):
            qs = qs.filter(academic_class_id=p["academic_class"])

        return qs

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(
            {"message": "Fee structure created.", "data": self.get_serializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = self.get_serializer(instance=obj, data=request.data, partial=False, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Fee structure updated.", "data": self.get_serializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = self.get_serializer(instance=obj, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "Fee structure updated.", "data": self.get_serializer(obj).data})

    # For delete: you can keep hard delete, or implement soft delete by setting status="deleted".
    # If you want soft delete, tell me and I’ll modify destroy().
    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        s = self.get_serializer(instance=obj, data={"status": "deleted"}, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"message": "Fee structure deleted."}, status=status.HTTP_200_OK)

