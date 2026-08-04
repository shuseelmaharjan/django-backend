from __future__ import annotations

from rest_framework import serializers
from .models import FeeHead
from schools.models import School
from academics.models import AcademicClass
from batch.models import AcademicBatch

from django.core.exceptions import ValidationError as DjangoValidationError

from fees.models import FeeStructure, FeeScope, FeeStatus
from fees.services.configuration import get_fee_configuration
from common.constants import Currency
from utils.get_school_id_by_token import get_school_for_user


class FeeHeadMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeHead
        fields = ["id", "name", "code", "group"]

class SchoolMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["id", "name", "code"]

class BatchMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicBatch
        fields = ["id", "name", "end_date_ad", "start_date_bs", "end_date_bs", "is_active"]

class AcademicClassMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicClass
        fields = ["id", "name"]


class FeeHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeHead
        fields = [
            "id",
            "name",
            "code",
            "group",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_code(self, value: str) -> str:
        # keep codes consistent (optional)
        return value.strip().lower()

class FeeStructureSerializer(serializers.ModelSerializer):
    # force read-only fields controlled by program
    school = serializers.UUIDField(source="school_id", read_only=True)
    currency = serializers.ChoiceField(choices=Currency.choices, read_only=True)

    fee_head_detail = FeeHeadMiniSerializer(source="fee_head", read_only=True)
    school_detail = SchoolMiniSerializer(source="school", read_only=True)
    batch_detail = BatchMiniSerializer(source="batch", read_only=True)
    academic_class_detail = AcademicClassMiniSerializer(source="academic_class", read_only=True)

    class Meta:
        model = FeeStructure
        fields = [
            "id",

            # ids
            "fee_head",
            "school",
            "batch",
            "academic_class",

            # details
            "fee_head_detail",
            "school_detail",
            "batch_detail",
            "academic_class_detail",

            "amount",
            "currency",
            "period",
            "status",
            "upgrade_impact",
            "scope",
            "tax_included",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "school",
            "currency",
            "fee_head_detail",
            "school_detail",
            "batch_detail",
            "academic_class_detail",
        ]

    def validate(self, attrs):
        """
        Enforce your scope rules + active uniqueness rule.
        Model.clean() also validates, but doing it here gives nicer API errors.
        """
        request = self.context["request"]
        school = get_school_for_user(request.user)

        # during update, attrs may not contain all fields
        instance: FeeStructure | None = getattr(self, "instance", None)

        scope = attrs.get("scope", instance.scope if instance else FeeScope.GLOBAL)
        batch = attrs.get("batch", instance.batch if instance else None)
        academic_class = attrs.get("academic_class", instance.academic_class if instance else None)
        fee_head = attrs.get("fee_head", instance.fee_head if instance else None)
        period = attrs.get("period", instance.period if instance else None)
        status = attrs.get("status", instance.status if instance else FeeStatus.active)

        # FeeHead active check (your model does too; keep here for clean error)
        if fee_head and not fee_head.is_active:
            raise serializers.ValidationError({"fee_head": ["This fee head is inactive and cannot be used."]})

        # Scope conditions (as per your latest message)
        if scope == FeeScope.GLOBAL:
            if batch is not None or academic_class is not None:
                raise serializers.ValidationError({"scope": ["GLOBAL cannot have batch/class set."]})

        elif scope == FeeScope.BATCH:
            if batch is None:
                raise serializers.ValidationError({"batch": ["Batch is required for BATCH scope."]})
            if academic_class is not None:
                raise serializers.ValidationError({"academic_class": ["Class must be empty for BATCH scope."]})

        elif scope == FeeScope.CLASS:
            if academic_class is None:
                raise serializers.ValidationError({"academic_class": ["Class is required for CLASS scope."]})
            if batch is not None:
                raise serializers.ValidationError({"batch": ["Batch must be empty for CLASS scope."]})

        elif scope == FeeScope.BATCH_CLASS:
            if batch is None:
                raise serializers.ValidationError({"batch": ["Batch is required for BATCH_CLASS scope."]})
            if academic_class is None:
                raise serializers.ValidationError({"academic_class": ["Class is required for BATCH_CLASS scope."]})

        else:
            raise serializers.ValidationError({"scope": ["Invalid scope value."]})

        # batch school consistency
        if batch is not None and batch.school_id != school.id:
            raise serializers.ValidationError({"batch": ["Batch does not belong to your school."]})

        # if both provided, ensure class belongs to same batch (your model also checks)
        if batch is not None and academic_class is not None:
            if academic_class.batch_id and academic_class.batch_id != batch.id:
                raise serializers.ValidationError(
                    {"academic_class": ["Class must belong to the selected batch."]}
                )

        # active uniqueness: prevent duplicates for same definition when status=active
        # (DB constraint will also enforce; this gives clean 400 instead of 500)
        if status == FeeStatus.active and fee_head and period:
            qs = FeeStructure.objects.filter(
                school=school,
                fee_head=fee_head,
                period=period,
                scope=scope,
                batch=batch,
                academic_class=academic_class,
                status=FeeStatus.active,
            )
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    "non_field_errors": ["An active fee structure already exists for this fee head + scope + period."]
                })

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        school = get_school_for_user(request.user)

        validated_data["school"] = school
        validated_data["currency"] = get_fee_configuration(school).currency

        try:
            obj = super().create(validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(getattr(e, "message_dict", {"detail": e.messages}))
        return obj

    def update(self, instance, validated_data):
        # keep school and currency controlled
        validated_data.pop("school", None)
        validated_data.pop("currency", None)

        try:
            obj = super().update(instance, validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(getattr(e, "message_dict", {"detail": e.messages}))
        return obj