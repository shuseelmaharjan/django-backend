from __future__ import annotations
from typing import Any, Dict

from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from academics.models import AcademicClass, Section
from batch.models import AcademicBatch
from utils.get_school_id_by_token import get_school_for_user


# ------------------------
# AcademicClass serializers
# ------------------------

class AcademicClassCreateSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    name = serializers.CharField(max_length=80)
    sort_order = serializers.IntegerField(required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        batch = AcademicBatch.objects.filter(id=attrs["batch_id"], school=school).first()
        if not batch:
            raise serializers.ValidationError({"batch_id": ["Invalid batch for your school."]})

        attrs["_batch"] = batch
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> AcademicClass:
        obj = AcademicClass(
            batch=validated_data["_batch"],
            name=validated_data["name"],
            sort_order=validated_data.get("sort_order", 0),
            is_active=validated_data.get("is_active", True),
        )
        obj.save()
        return obj


class AcademicClassUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False)
    sort_order = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def update(self, instance: AcademicClass, validated_data: Dict[str, Any]) -> AcademicClass:
        for f in ["name", "sort_order", "is_active"]:
            if f in validated_data:
                setattr(instance, f, validated_data[f])
        instance.save()
        return instance


class AcademicClassReadSerializer(serializers.ModelSerializer):
    batch_id = serializers.IntegerField(source="batch.id", read_only=True)
    school_id = serializers.UUIDField(source="batch.school.id", read_only=True)
    school_code = serializers.CharField(source="batch.school.code", read_only=True)

    class Meta:
        model = AcademicClass
        fields = [
            "id", "batch_id", "school_id", "school_code",
            "name", "sort_order", "is_active", "created_at"
        ]


# ------------------------
# Section serializers
# ------------------------

class SectionCreateSerializer(serializers.Serializer):
    academic_class_id = serializers.UUIDField()
    name = serializers.CharField(max_length=30)
    sort_order = serializers.IntegerField(required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        # Ensure academic_class belongs to user's school via batch -> school
        academic_class = (
            AcademicClass.objects
            .select_related("batch__school")
            .filter(id=attrs["academic_class_id"], batch__school=school)
            .first()
        )
        if not academic_class:
            raise serializers.ValidationError({"academic_class_id": ["Invalid class for your school."]})

        attrs["_academic_class"] = academic_class
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Section:
        obj = Section(
            academic_class=validated_data["_academic_class"],
            name=validated_data["name"],
            sort_order=validated_data.get("sort_order", 0),
            is_active=validated_data.get("is_active", True),
        )
        obj.save()
        return obj


class SectionUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=30, required=False)
    sort_order = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def update(self, instance: Section, validated_data: Dict[str, Any]) -> Section:
        for f in ["name", "sort_order", "is_active"]:
            if f in validated_data:
                setattr(instance, f, validated_data[f])
        instance.save()
        return instance


class SectionReadSerializer(serializers.ModelSerializer):
    academic_class_id = serializers.UUIDField(source="academic_class.id", read_only=True)
    batch_id = serializers.IntegerField(source="academic_class.batch.id", read_only=True)

    class Meta:
        model = Section
        fields = [
            "id", "academic_class_id", "batch_id",
            "name", "sort_order", "is_active", "created_at"
        ]
