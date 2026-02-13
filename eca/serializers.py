from __future__ import annotations
from typing import Any, Dict

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from fees.models import FeeStructure
from schools.models import School
from .models import EcaActivities, EcaActivityStatus
from utils.get_school_id_by_token import get_school_for_user


class SchoolMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["id", "name", "code"]


class FeeStructureMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        # adjust fields if your FeeStructure differs
        fields = ["id", "amount", "currency", "period", "status", "scope", "created_at"]


class EcaActivityCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    fees = serializers.PrimaryKeyRelatedField(
        queryset=FeeStructure.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        attrs["name"] = attrs["name"].strip()
        if not attrs["name"]:
            raise serializers.ValidationError({"name": ["This field may not be blank."]})

        request = self.context["request"]
        school = get_school_for_user(request.user)

        fee = attrs.get("fees")
        if fee is not None and hasattr(fee, "school_id") and fee.school_id != school.id:
            raise serializers.ValidationError({"fees": ["Fee structure does not belong to your school."]})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> EcaActivities:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        obj = EcaActivities(
            school=school,
            name=validated_data["name"],
            description=validated_data.get("description", ""),
            fees=validated_data.get("fees"),
            status=EcaActivityStatus.active,
        )

        try:
            obj.save()
        except DjangoValidationError as e:
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError({"detail": e.messages})

        return obj


class EcaActivityUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    fees = serializers.PrimaryKeyRelatedField(
        queryset=FeeStructure.objects.all(),
        required=False,
        allow_null=True,
    )
    status = serializers.ChoiceField(choices=EcaActivityStatus.choices, required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in attrs:
            attrs["name"] = attrs["name"].strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["This field may not be blank."]})

        request = self.context["request"]
        school = get_school_for_user(request.user)

        fee = attrs.get("fees")
        if fee is not None and hasattr(fee, "school_id") and fee.school_id != school.id:
            raise serializers.ValidationError({"fees": ["Fee structure does not belong to your school."]})

        return attrs

    def update(self, instance: EcaActivities, validated_data: Dict[str, Any]) -> EcaActivities:
        for f in ["name", "description", "fees", "status"]:
            if f in validated_data:
                setattr(instance, f, validated_data[f])

        try:
            instance.save()
        except DjangoValidationError as e:
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError({"detail": e.messages})

        return instance


class EcaActivityReadSerializer(serializers.ModelSerializer):
    school_detail = SchoolMiniSerializer(source="school", read_only=True)
    fees_detail = FeeStructureMiniSerializer(source="fees", read_only=True)

    class Meta:
        model = EcaActivities
        fields = [
            "id",
            "name",
            "description",
            "school",
            "fees",
            "school_detail",
            "fees_detail",
            "status",
            "created_at",
            "updated_at",
        ]
