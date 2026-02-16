from __future__ import annotations

from rest_framework import serializers

from batch.models import AcademicBatch
from fees.models import FeeStructure
from fees.serializers import (
    FeeHeadMiniSerializer,
    SchoolMiniSerializer,
    AcademicClassMiniSerializer,
)
from common.constants import Currency


class AcademicBatchFullSerializer(serializers.ModelSerializer):
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
            "status",
            "school",
            "created_at",
            "updated_at",
        ]


class FeeStructureApplicableSerializer(serializers.ModelSerializer):
    school = serializers.UUIDField(source="school_id", read_only=True)
    currency = serializers.ChoiceField(choices=Currency.choices, read_only=True)

    fee_head_detail = FeeHeadMiniSerializer(source="fee_head", read_only=True)
    school_detail = SchoolMiniSerializer(source="school", read_only=True)

    # keep these as-is (fee structures may be global => null)
    batch_detail = AcademicBatchFullSerializer(source="batch", read_only=True)
    academic_class_detail = AcademicClassMiniSerializer(source="academic_class", read_only=True)

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "fee_head",
            "school",
            "batch",
            "academic_class",

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
        read_only_fields = fields
