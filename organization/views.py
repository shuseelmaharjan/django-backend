from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from common.mixins import ListFilterMetaMixin
from .models import School, SchoolSetting
from .serializers import SchoolSerializer, SchoolSettingSerializer
from common.permissions import IsSuperUser
import django_filters


class SchoolFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        method="filter_status",
        choices=(("active", "active"), ("inactive", "inactive"), ("all", "all")),
    )

    created_at__gte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_at__lte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = School
        fields = ["status", "created_at__gte", "created_at__lte"]

    def filter_status(self, queryset, name, value):
        if value == "active":
            return queryset.filter(is_active=True)
        if value == "inactive":
            return queryset.filter(is_active=False)
        return queryset

@extend_schema(tags=["02. Organization"])
class SchoolViewSet(ListFilterMetaMixin, viewsets.ModelViewSet):
    queryset = School.objects.all().order_by("-created_at")
    serializer_class = SchoolSerializer
    permission_classes = [IsSuperUser]
    lookup_field = "id"

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SchoolFilter
    search_fields = ["name", "code", "email", "phone"]
    ordering_fields = ["created_at", "name", "code"]
    ordering = ["-created_at"]

    public_filter_meta = {
        "status": {
            "type": "choice",
            "choices": ["active", "inactive", "all"],
        }
    }

    public_sort_meta = {
        "sort_by": ["created_at", "name", "code"],
        "sort_order": ["asc", "desc"],
    }
    @action(detail=False, methods=["get"])
    def active(self, request):
        school = School.objects.filter(is_active=True).first()
        if not school:
            return Response({"detail": "No active school found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(school).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def activate(self, request, id=None):
        school = self.get_object()
        if not school.is_active:
            school.is_active = True
            school.save()
        return Response(self.get_serializer(school).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, id=None):
        school = self.get_object()
        if school.is_active:
            school.is_active = False
            school.save()
        return Response(self.get_serializer(school).data, status=status.HTTP_200_OK)


@extend_schema(tags=["02. Organization"])
class SchoolSettingViewSet(viewsets.ModelViewSet):
    queryset = SchoolSetting.objects.all().select_related("school")
    serializer_class = SchoolSettingSerializer
    permission_classes = [IsSuperUser]
    lookup_field = "id"

    @action(detail=False, methods=["get"])
    def active(self, request):
        setting = SchoolSetting.objects.filter(is_active=True).select_related("school").first()
        if not setting:
            return Response({"detail": "No active school setting found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(setting).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def activate(self, request, id=None):
        setting = self.get_object()
        if not setting.is_active:
            setting.is_active = True
            setting.save()
        return Response(self.get_serializer(setting).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, id=None):
        setting = self.get_object()
        if setting.is_active:
            setting.is_active = False
            setting.save()
        return Response(self.get_serializer(setting).data, status=status.HTTP_200_OK)
