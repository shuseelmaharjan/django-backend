from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import School, SchoolSetting
from .serializers import SchoolSerializer, SchoolSettingSerializer


@extend_schema(tags=["02. Organization"])
class SchoolViewSet(viewsets.ModelViewSet):
    """
    CRUD for School (single-organization aware)
    """
    queryset = School.objects.all().order_by("-created_at")
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    @action(detail=False, methods=["get"])
    def active(self, request):
        active_school = School.objects.filter(is_active=True).first()
        if not active_school:
            return Response(
                {"detail": "No active school found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self.get_serializer(active_school).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, id=None):
        school = self.get_object()
        school.is_active = True
        school.save()
        return Response(self.get_serializer(school).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, id=None):
        school = self.get_object()
        school.is_active = False
        school.save()
        return Response(self.get_serializer(school).data)


@extend_schema(tags=["02. Organization"])
class SchoolSettingViewSet(viewsets.ModelViewSet):
    """
    CRUD for SchoolSetting (one active globally)
    """
    queryset = SchoolSetting.objects.all().select_related("school")
    serializer_class = SchoolSettingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    @action(detail=False, methods=["get"])
    def active(self, request):
        active_setting = SchoolSetting.objects.filter(is_active=True).first()
        if not active_setting:
            return Response(
                {"detail": "No active school setting found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self.get_serializer(active_setting).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, id=None):
        setting = self.get_object()
        setting.is_active = True
        setting.save()
        return Response(self.get_serializer(setting).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, id=None):
        setting = self.get_object()
        setting.is_active = False
        setting.save()
        return Response(self.get_serializer(setting).data)
