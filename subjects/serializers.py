# subjects/serializers.py
from __future__ import annotations

from rest_framework import serializers

from subjects.models import Subject, SubjectStatus
from django.db.models import Q


class SubjectReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "code",
            "description",
            "sort_order",
            "status",
            "created_at",
            "updated_at",
        ]


class SubjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "description",
            "sort_order",
            "status",
        ]

    def validate_name(self, value: str):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Name is required.")
        return v

    def validate_code(self, value: str):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Code is required.")

        # allow duplicates if the existing one is deleted
        qs = Subject.objects.filter(code__iexact=v).exclude(status=SubjectStatus.DELETED)

        if getattr(self, "instance", None):
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Subject code already exists.")
        return v

    def validate_status(self, value: str):
        if value not in SubjectStatus.values:
            raise serializers.ValidationError("Invalid status.")
        return value


class SubjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "description",
            "sort_order",
            "status",
        ]

    def validate_name(self, value: str):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Name is required.")
        return v

    def validate_code(self, value: str):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Code is required.")

        # allow duplicates if the existing one is deleted
        qs = Subject.objects.filter(code__iexact=v).exclude(status=SubjectStatus.DELETED)

        if getattr(self, "instance", None):
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Subject code already exists.")
        return v

    def validate_status(self, value: str):
        if value not in SubjectStatus.values:
            raise serializers.ValidationError("Invalid status.")
        return value


class SubjectReorderItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sort_order = serializers.IntegerField(min_value=0)


class SubjectReorderSerializer(serializers.Serializer):
    items = SubjectReorderItemSerializer(many=True)

    def validate(self, attrs):
        ids = [x["id"] for x in attrs["items"]]
        qs_count = Subject.objects.filter(id__in=ids).count()
        if qs_count != len(ids):
            raise serializers.ValidationError("Some subjects not found.")
        return attrs

    def save(self, **kwargs):
        items = self.validated_data["items"]

        objs = Subject.objects.in_bulk([x["id"] for x in items])

        for row in items:
            obj = objs[row["id"]]
            obj.sort_order = row["sort_order"]

        Subject.objects.bulk_update(objs.values(), ["sort_order"])

        return {"updated": len(items)}


class SubjectStatusToggleSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[SubjectStatus.ACTIVE, SubjectStatus.INACTIVE])

    def save(self, subject: Subject, **kwargs):
        subject.status = self.validated_data["status"]
        subject.save(update_fields=["status", "updated_at"])
        return subject

