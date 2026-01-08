from rest_framework import serializers
from fees.models import (
    FeeHead, FeePlan, FeeRule,
    StudentFeeOption, StudentFeeOverride, StudentCharge
)

class FeeHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeHead
        fields = ["id", "code", "school_id", "name", "frequency", "is_optional", "is_refundable", "is_active"]
        read_only_fields = ["id", "school_id"]

class FeePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeePlan
        fields = ["id", "school_id", "academic_year", "name", "is_active", "created_at"]
        read_only_fields = ["id", "school_id", "created_at"]

class FeeRuleSerializer(serializers.ModelSerializer):
    fee_head_code = serializers.CharField(source="fee_head.code", read_only=True)

    class Meta:
        model = FeeRule
        fields = [
            "id", "plan", "fee_head", "fee_head_code",
            "target_type", "target_id",
            "calc_type", "amount", "unit_name", "unit_price",
            "months_csv", "term_codes_csv", "exam_codes_csv",
            "is_mandatory",
            "active_from", "active_to", "is_active",
            "priority",
        ]
        read_only_fields = ["id"]

class StudentFeeOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentFeeOption
        fields = ["id", "student", "fee_head", "is_enabled", "units", "support_document"]
        read_only_fields = ["id"]

class StudentFeeOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentFeeOverride
        fields = [
            "id", "student", "fee_head",
            "override_amount", "discount_amount", "discount_percent",
            "is_waived", "reason", "proof_file",
        ]
        read_only_fields = ["id"]

class StudentChargeSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    fee_head_code = serializers.CharField(source="fee_head.code", read_only=True)

    class Meta:
        model = StudentCharge
        fields = [
            "id", "student", "student_email",
            "academic_year",
            "fee_head", "fee_head_code",
            "month", "term_code", "exam_code",
            "base_amount", "discount_amount", "final_amount",
            "status", "generated_from_rule", "generated_at",
        ]
        read_only_fields = ["id", "generated_at"]
