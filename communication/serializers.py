from rest_framework import serializers
from communication.models import Notice, MessageLog


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = [
            "id", "school_id",
            "title", "body",
            "target_type", "target_id",
            "published_at",
            "created_by", "created_at",
        ]
        read_only_fields = ["id", "school_id", "published_at", "created_by", "created_at"]


class NoticeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ["title", "body", "target_type", "target_id"]


class MessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageLog
        fields = [
            "id", "school_id",
            "channel", "to", "provider",
            "payload", "status",
            "sent_at", "error",
            "created_at",
        ]
        read_only_fields = ["id", "school_id", "created_at"]
