from __future__ import annotations

from rest_framework import serializers
from django.db.models import Q

from accounts.models import User
from academics.models import StudentEnrollments
from batch.models import AcademicBatch
from billing.models import Billing
from fees.models import FeeStructure, FeeInclude, StudentFeeWallet, FeeIncludeAudit
from common.constants import UserRole

# Reuse your existing ones if you want:
# from profiles.serializers_student_list import ProfileSerializer
# from profiles.serializers_student_list import StudentEnrollmentMiniSerializer
from profiles.serializers_student_list import ProfileSerializer
from filehandler.serializers import UploadedFileSerializer


# --------------------------
# Small helpers
# --------------------------

class BatchMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicBatch
        fields = [
            "id",
            "name",
            "start_date_bs",
            "start_date_ad",
            "end_date_bs",
            "end_date_ad",
            "status",
            "is_active",
        ]


class AcademicClassMiniSerializer(serializers.Serializer):
    # because AcademicClass is UUID; simple mapping is enough
    id = serializers.UUIDField()
    name = serializers.CharField()


class SectionMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class EnrollmentSerializer(serializers.ModelSerializer):
    batch = BatchMiniSerializer(read_only=True)
    academic_class = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()

    class Meta:
        model = StudentEnrollments
        fields = [
            "id",
            "status",
            "enrolled_at",
            "batch",
            "academic_class",
            "section",
        ]

    def get_academic_class(self, obj: StudentEnrollments):
        if not obj.academic_class_id:
            return None
        return {"id": obj.academic_class_id, "name": getattr(obj.academic_class, "name", "")}

    def get_section(self, obj: StudentEnrollments):
        if not obj.section_id:
            return None
        return {"id": obj.section_id, "name": getattr(obj.section, "name", "")}


class BillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Billing
        fields = [
            "id",
            "amount",
            "inwords",
            "description",
            "created_at",
            "status",
            "payment_method",
            "receipt_number",
            "received_by",
        ]


class FeeHeadMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField()
    group = serializers.CharField()


class FeeStructureSerializer(serializers.ModelSerializer):
    fee_head_detail = serializers.SerializerMethodField()

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "fee_head",
            "fee_head_detail",
            "amount",
            "currency",
            "period",
            "status",
            "scope",
            "tax_included",
            "batch",
            "academic_class",
            "created_at",
            "updated_at",
        ]

    def get_fee_head_detail(self, obj: FeeStructure):
        fh = getattr(obj, "fee_head", None)
        if not fh:
            return None
        return {
            "id": fh.id,
            "name": fh.name,
            "code": fh.code,
            "group": fh.group,
        }


class FeeIncludeSerializer(serializers.ModelSerializer):
    fee_detail = FeeStructureSerializer(source="fees", read_only=True)

    class Meta:
        model = FeeInclude
        fields = [
            "id",
            "fees",
            "fee_detail",
            "user",
            "batch",
            "classroom",
            "status",
            "created_at",
        ]


class StudentFeeWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentFeeWallet
        fields = [
            "id",
            "student",
            "batch",
            "academic_class",
            "total_payable",
            "total_paid",
            "total_discount",
            "total_scholarship",
            "total_due",
            "updated_at",
        ]


class FeeIncludeAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeIncludeAudit
        fields = [
            "id",
            "fee_include",
            "actor",
            "action",
            "prev_status",
            "new_status",
            "prev_batch_id",
            "new_batch_id",
            "prev_class_id",
            "new_class_id",
            "created_at",
        ]


# --------------------------
# Summary (LIST) serializer
# --------------------------

class Student360SummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_id = serializers.SerializerMethodField()
    profile_picture = UploadedFileSerializer(source="profile_picture_file", read_only=True)

    # dynamic meta
    batches_meta = serializers.SerializerMethodField()
    current_enrollment = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "role",
            "status",
            "username",
            "profile_id",
            "profile_picture",
            "current_enrollment",
            "batches_meta",
        ]

    def get_full_name(self, obj: User) -> str:
        parts = [obj.first_name, getattr(obj, "middle_name", ""), obj.last_name]
        return " ".join([p for p in parts if p]).strip()

    def get_profile_id(self, obj: User):
        prof = getattr(obj, "profile", None)
        return getattr(prof, "id", None)

    def get_current_enrollment(self, obj: User):
        enrollments = list(getattr(obj, "enrollments", []).all())
        if not enrollments:
            return None
        e = enrollments[0]
        return {
            "id": e.id,
            "status": e.status,
            "enrolled_at": e.enrolled_at,
            "batch_id": e.batch_id,
            "batch_name": getattr(e.batch, "name", None),
            "academic_class_id": e.academic_class_id,
            "class_name": getattr(e.academic_class, "name", None),
            "section_id": e.section_id,
            "section_name": getattr(e.section, "name", None),
        }

    def get_batches_meta(self, obj: User):
        """
        Returns which batches student existed in (unique) + last status per batch.
        """
        enrollments = list(getattr(obj, "enrollments", []).all())
        by_batch = {}
        for e in enrollments:
            bid = e.batch_id
            if not bid:
                continue
            # enrollments are prefetched ordered by -enrolled_at, so first seen per batch is latest
            if bid not in by_batch:
                by_batch[bid] = {
                    "batch_id": bid,
                    "batch_name": getattr(e.batch, "name", None),
                    "latest_status": e.status,
                    "latest_enrolled_at": e.enrolled_at,
                }
        return {
            "count": len(by_batch),
            "items": list(by_batch.values()),
        }


# --------------------------
# Detail (RETRIEVE) serializer
# --------------------------

class Student360DetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_id = serializers.SerializerMethodField()
    profile = ProfileSerializer(read_only=True)
    profile_picture = UploadedFileSerializer(source="profile_picture_file", read_only=True)

    # main relations
    enrollments = EnrollmentSerializer(many=True, read_only=True)

    # batch-scoped payloads (prepared in view via context)
    billings = serializers.SerializerMethodField()
    fee_structures = serializers.SerializerMethodField()
    fee_includes = serializers.SerializerMethodField()
    wallets = serializers.SerializerMethodField()
    fee_include_audits = serializers.SerializerMethodField()

    # meta: which batches existed
    batches_meta = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "role",
            "status",
            "username",
            "profile_id",
            "profile",
            "profile_picture",
            "batches_meta",
            "enrollments",
            "billings",
            "fee_structures",
            "fee_includes",
            "wallets",
            "fee_include_audits",
        ]

    def get_full_name(self, obj: User) -> str:
        parts = [obj.first_name, getattr(obj, "middle_name", ""), obj.last_name]
        return " ".join([p for p in parts if p]).strip()

    def get_profile_id(self, obj: User):
        prof = getattr(obj, "profile", None)
        return getattr(prof, "id", None)

    def get_batches_meta(self, obj: User):
        # reuse from summary
        return Student360SummarySerializer(obj, context=self.context).data.get("batches_meta")

    def get_billings(self, obj: User):
        qs = self.context.get("billings_qs")
        if qs is None:
            return []
        return BillingSerializer(qs, many=True, context=self.context).data

    def get_fee_structures(self, obj: User):
        qs = self.context.get("fee_structures_qs")
        if qs is None:
            return []
        return FeeStructureSerializer(qs, many=True, context=self.context).data

    def get_fee_includes(self, obj: User):
        qs = self.context.get("fee_includes_qs")
        if qs is None:
            return []
        return FeeIncludeSerializer(qs, many=True, context=self.context).data

    def get_wallets(self, obj: User):
        qs = self.context.get("wallets_qs")
        if qs is None:
            return []
        return StudentFeeWalletSerializer(qs, many=True, context=self.context).data

    def get_fee_include_audits(self, obj: User):
        qs = self.context.get("fee_include_audits_qs")
        if qs is None:
            return []
        return FeeIncludeAuditSerializer(qs, many=True, context=self.context).data
