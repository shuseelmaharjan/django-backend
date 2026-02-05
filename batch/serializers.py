from __future__ import annotations
from typing import Any, Dict

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import AcademicBatch
from utils.dates import bs_to_ad
from utils.get_school_id_by_token import get_school_for_user


class AcademicBatchCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    start_date_bs = serializers.CharField(max_length=10)
    end_date_bs = serializers.CharField(max_length=10)
    is_active = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        # validate BS format + logical order (actual overlap handled in model clean)
        try:
            start_ad = bs_to_ad(attrs["start_date_bs"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"start_date_bs": e.messages})

        try:
            end_ad = bs_to_ad(attrs["end_date_bs"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"end_date_bs": e.messages})

        if start_ad > end_ad:
            raise serializers.ValidationError({"end_date_bs": ["end_date must be >= start_date."]})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> AcademicBatch:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        batch = AcademicBatch(
            school=school,
            name=validated_data["name"],
            start_date_bs=validated_data["start_date_bs"],
            end_date_bs=validated_data["end_date_bs"],
            is_active=validated_data.get("is_active", False),
        )
        batch.save()
        return batch


class AcademicBatchUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    start_date_bs = serializers.CharField(max_length=10, required=False)
    end_date_bs = serializers.CharField(max_length=10, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        bs_start_provided = "start_date_bs" in attrs
        bs_end_provided = "end_date_bs" in attrs

        if bs_start_provided ^ bs_end_provided:
            raise serializers.ValidationError(
                {"start_date_bs": ["Provide both start_date_bs and end_date_bs to change range."],
                 "end_date_bs": ["Provide both start_date_bs and end_date_bs to change range."]}
            )

        if bs_start_provided and bs_end_provided:
            try:
                start_ad = bs_to_ad(attrs["start_date_bs"])
            except DjangoValidationError as e:
                raise serializers.ValidationError({"start_date_bs": e.messages})

            try:
                end_ad = bs_to_ad(attrs["end_date_bs"])
            except DjangoValidationError as e:
                raise serializers.ValidationError({"end_date_bs": e.messages})

            if start_ad > end_ad:
                raise serializers.ValidationError({"end_date_bs": ["end_date must be >= start_date."]})

        return attrs

    def update(self, instance: AcademicBatch, validated_data: Dict[str, Any]) -> AcademicBatch:
        for f in ["name", "start_date_bs", "end_date_bs", "is_active"]:
            if f in validated_data:
                setattr(instance, f, validated_data[f])

        instance.save()
        return instance


class AcademicBatchReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicBatch
        fields = [
            "id",
            "name",
            "start_date_bs",
            "start_date_ad",
            "end_date_bs",
            "end_date_ad",
            "is_active",
            "school",
            "created_at",
            "updated_at",
        ]
