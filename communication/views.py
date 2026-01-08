from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from accounts.permissions import IsSchoolAdmin
from common.viewsets import SchoolScopedModelViewSet
from communication.models import Notice, MessageLog
from communication.serializers import (
    NoticeSerializer, NoticeCreateSerializer,
    MessageLogSerializer,
)


@extend_schema(tags=["11. Communication"])
class NoticeViewSet(SchoolScopedModelViewSet):
    """
    Admin creates/publishes notices.
    Later: teachers/students can read published notices based on target resolution.
    """
    queryset = Notice.objects.all().order_by("-created_at")
    serializer_class = NoticeSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_serializer_class(self):
        if self.action == "create":
            return NoticeCreateSerializer
        return NoticeSerializer

    def perform_create(self, serializer):
        serializer.save(
            school_id=self.request.school_id,
            created_by=self.request.user,
        )

    def get_queryset(self):
        qs = super().get_queryset()
        target_type = self.request.query_params.get("target_type")
        target_id = self.request.query_params.get("target_id")
        published = self.request.query_params.get("published")

        if target_type:
            qs = qs.filter(target_type=target_type)
        if target_id:
            qs = qs.filter(target_id=target_id)
        if published in ("true", "false"):
            qs = qs.filter(published_at__isnull=(published == "false"))
        return qs

    @action(detail=True, methods=["post"])
    def publish(self, request, id=None):
        obj = self.get_object()
        obj.publish()
        return Response({"detail": "Published", "published_at": obj.published_at}, status=status.HTTP_200_OK)


@extend_schema(tags=["11. Communication"])
class MessageLogViewSet(SchoolScopedModelViewSet):
    """
    Read-only log for admin: sms/email/push delivery.
    You will create logs from your notification service later.
    """
    queryset = MessageLog.objects.all().order_by("-created_at")
    serializer_class = MessageLogSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        channel = self.request.query_params.get("channel")
        to = self.request.query_params.get("to")
        status_ = self.request.query_params.get("status")

        if channel:
            qs = qs.filter(channel=channel)
        if to:
            qs = qs.filter(to__icontains=to)
        if status_:
            qs = qs.filter(status=status_)
        return qs
