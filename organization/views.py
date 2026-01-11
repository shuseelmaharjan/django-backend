from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import School, Campus, SchoolSetting
from .serializers import SchoolSerializer, CampusSerializer, SchoolSettingSerializer

@extend_schema(tags=["02. Organization"])
class SchoolViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for School model
    """
    queryset = School.objects.all().order_by('-created_at')
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get the currently active school"""
        active_school = School.objects.filter(is_active=True).first()
        if not active_school:
            return Response(
                {"detail": "No active school found. "},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(active_school)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, id=None):
        """Activate a specific school (deactivates others)"""
        school = self.get_object()
        school.is_active = True
        school.save()
        serializer = self.get_serializer(school)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, id=None):
        """Deactivate a specific school"""
        school = self.get_object()
        school.is_active = False
        school.save()
        serializer = self.get_serializer(school)
        return Response(serializer.data)

@extend_schema(tags=["02. Organization"])
class CampusViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Campus model
    """
    queryset = Campus.objects.all().select_related('school')
    serializer_class = CampusSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        """Filter by school if provided"""
        queryset = super().get_queryset()
        school_id = self.request.query_params.get('school', None)
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        return queryset

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active campuses (optionally filtered by school)"""
        school_id = request.query_params.get('school', None)
        queryset = Campus.objects.filter(is_active=True)
        if school_id:
            queryset = queryset.filter(school_id=school_id)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, id=None):
        """Activate a specific campus (deactivates others for same school)"""
        campus = self.get_object()
        campus.is_active = True
        campus.save()
        serializer = self.get_serializer(campus)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, id=None):
        """Deactivate a specific campus"""
        campus = self.get_object()
        campus.is_active = False
        campus.save()
        serializer = self.get_serializer(campus)
        return Response(serializer.data)

@extend_schema(tags=["02. Organization"])
class SchoolSettingViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for SchoolSetting model
    """
    queryset = SchoolSetting.objects.all().select_related('school')
    serializer_class = SchoolSettingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get the currently active school setting"""
        active_setting = SchoolSetting.objects.filter(is_active=True).first()
        if not active_setting:
            return Response(
                {"detail": "No active school setting found."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(active_setting)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, id=None):
        """Activate a specific school setting (deactivates others)"""
        setting = self.get_object()
        setting.is_active = True
        setting.save()
        serializer = self.get_serializer(setting)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, id=None):
        """Deactivate a specific school setting"""
        setting = self.get_object()
        setting.is_active = False
        setting.save()
        serializer = self.get_serializer(setting)
        return Response(serializer.data)