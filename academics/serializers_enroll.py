from __future__ import annotations

from decimal import Decimal
from typing import List

from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from utils.get_school_id_by_token import get_school_for_user

from accounts.models import User
from common.constants import UserRole, UserStatus

from academics.models import AcademicClass, Section, StudentEnrollments, EnrollmentStatus
from batch.models import AcademicBatch

from fees.models import FeeStructure, FeeStatus, FeeScope, FeeInclude, StudentFeeWallet, FeeIncludeAudit, FeeIncludeAuditAction
from profiles.models import Profile


def _decimalize(v) -> Decimal:
    if v is None or v == "":
        return Decimal("0.00")
    return Decimal(str(v))


def _fee_structure_applicable(fs: FeeStructure, batch: AcademicBatch, academic_class: AcademicClass) -> bool:
    """
    Accepts both your older model.clean rules and the serializer rules you shared (which differ for CLASS).
    """
    if fs.status != FeeStatus.active:
        return False

    if fs.scope == FeeScope.GLOBAL:
        return fs.batch_id is None and fs.academic_class_id is None

    if fs.scope == FeeScope.BATCH:
        return fs.batch_id == batch.id and fs.academic_class_id is None

    if fs.scope == FeeScope.CLASS:
        # Some code paths expect batch empty; some expect batch+class.
        # We'll accept either:
        # - class matches and batch is NULL
        # - class matches and batch matches
        return fs.academic_class_id == academic_class.id and (fs.batch_id is None or fs.batch_id == batch.id)

    if fs.scope == FeeScope.BATCH_CLASS:
        return fs.batch_id == batch.id and fs.academic_class_id == academic_class.id

    return False


class StudentEnrollAndSetupFeesSerializer(serializers.Serializer):
    """
    POST payload:
    {
      "student": "<uuid>",
      "batch": 1,
      "academic_class": "<uuid>",
      "section": "<uuid|null>",
      "fee_structures": ["<uuid>", "<uuid>", ...],

      "total_payable_amount": "10000.00",
      "discounted_amount": "500.00",
      "scholarship_amount": "1000.00"
    }
    """
    student = serializers.UUIDField()
    batch = serializers.IntegerField()
    academic_class = serializers.UUIDField()
    section = serializers.UUIDField(required=False, allow_null=True)

    fee_structures = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
        required=False,
        default=list,
    )

    total_payable_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    discounted_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("0.00"))
    scholarship_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("0.00"))

    def validate(self, attrs):
        request = self.context["request"]
        school = get_school_for_user(request.user)

        # --- Load core objects ---
        try:
            student = User.objects.get(id=attrs["student"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"student": ["Student user not found."]})

        # Ensure it's a student role (if you want strictness)
        if getattr(student, "role", None) != UserRole.STUDENT:
            raise serializers.ValidationError({"student": ["User is not a student."]})

        try:
            batch = AcademicBatch.objects.select_related("school").get(id=attrs["batch"])
        except AcademicBatch.DoesNotExist:
            raise serializers.ValidationError({"batch": ["Batch not found."]})

        if batch.school_id != school.id:
            raise serializers.ValidationError({"batch": ["Batch does not belong to your school."]})

        try:
            academic_class = AcademicClass.objects.select_related("batch").get(id=attrs["academic_class"])
        except AcademicClass.DoesNotExist:
            raise serializers.ValidationError({"academic_class": ["Class not found."]})

        # Class must belong to same batch
        if academic_class.batch_id != batch.id:
            raise serializers.ValidationError({"academic_class": ["Class does not belong to the selected batch."]})

        section = None
        section_id = attrs.get("section", None)
        if section_id:
            try:
                section = Section.objects.get(id=section_id)
            except Section.DoesNotExist:
                raise serializers.ValidationError({"section": ["Section not found."]})
            if section.academic_class_id != academic_class.id:
                raise serializers.ValidationError({"section": ["Section must belong to the selected class."]})

        # Student must belong to same school (via Profile.school)
        profile = Profile.objects.select_related("school").filter(user=student).first()
        if not profile or profile.school_id != school.id:
            raise serializers.ValidationError({"student": ["Student does not belong to your school."]})

        # --- Validate fee_structures ---
        fee_ids: List[str] = attrs.get("fee_structures") or []
        fee_structures = []
        if fee_ids:
            fee_structures = list(
                FeeStructure.objects.select_related("school", "batch", "academic_class")
                .filter(id__in=fee_ids, school_id=school.id)
            )
            found = {str(x.id) for x in fee_structures}
            missing = [str(x) for x in fee_ids if str(x) not in found]
            if missing:
                raise serializers.ValidationError({"fee_structures": [f"Some fee structures not found in your school: {missing}"]})

            # applicability check
            not_applicable = [str(fs.id) for fs in fee_structures if not _fee_structure_applicable(fs, batch, academic_class)]
            if not_applicable:
                raise serializers.ValidationError({"fee_structures": [f"Some fee structures are not applicable to this batch/class or are inactive: {not_applicable}"]})

        # totals sanity
        total_payable = _decimalize(attrs["total_payable_amount"])
        discount = _decimalize(attrs.get("discounted_amount", Decimal("0.00")))
        scholarship = _decimalize(attrs.get("scholarship_amount", Decimal("0.00")))

        if total_payable < 0 or discount < 0 or scholarship < 0:
            raise serializers.ValidationError({"non_field_errors": ["Amounts must be >= 0."]})

        if discount + scholarship > total_payable:
            raise serializers.ValidationError({"non_field_errors": ["Discount + scholarship cannot exceed total payable."]})

        # attach resolved objects for create()
        attrs["_student_obj"] = student
        attrs["_batch_obj"] = batch
        attrs["_class_obj"] = academic_class
        attrs["_section_obj"] = section
        attrs["_fee_structures_obj"] = fee_structures
        attrs["_school_obj"] = school

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        actor = request.user

        student: User = validated_data["_student_obj"]
        batch: AcademicBatch = validated_data["_batch_obj"]
        academic_class: AcademicClass = validated_data["_class_obj"]
        section: Section | None = validated_data["_section_obj"]
        fee_structures: list[FeeStructure] = validated_data["_fee_structures_obj"]

        total_payable = _decimalize(validated_data["total_payable_amount"])
        discount = _decimalize(validated_data.get("discounted_amount", Decimal("0.00")))
        scholarship = _decimalize(validated_data.get("scholarship_amount", Decimal("0.00")))

        # 1) Create (or update) enrollment row
        enrollment, created = StudentEnrollments.objects.get_or_create(
            batch=batch,
            student=student,
            academic_class=academic_class,
            defaults={
                "section": section,
                "status": EnrollmentStatus.ENROLLED,
            },
        )

        # If exists, ensure status + section reflect request
        update_fields = []
        if enrollment.status != EnrollmentStatus.ENROLLED:
            enrollment.status = EnrollmentStatus.ENROLLED
            update_fields.append("status")

        # only update section if provided in request (including explicit null)
        if "section" in self.initial_data:
            enrollment.section = section
            update_fields.append("section")

        if update_fields:
            enrollment.save(update_fields=update_fields)

        # 2) Activate user from draft/inactive -> active
        # (You said: user.status active from draft, so we enforce ACTIVE + is_active True)
        user_update_fields = []
        if getattr(student, "status", None) != UserStatus.ACTIVE:
            student.status = UserStatus.ACTIVE
            user_update_fields.append("status")
        if student.is_active is not True:
            student.is_active = True
            user_update_fields.append("is_active")
        if user_update_fields:
            student.save(update_fields=user_update_fields)

        # 3) FeeInclude setup (create includes for selected fee structures)
        created_includes: list[FeeInclude] = []
        for fs in fee_structures:
            fi, fi_created = FeeInclude.objects.get_or_create(
                fees=fs,
                user=student,
                batch=batch,
                classroom=academic_class,
                defaults={"status": FeeStatus.active},
            )
            if not fi_created:
                # If previously soft-deleted, revive it
                if fi.status == FeeStatus.deleted:
                    prev = fi.status
                    fi.status = FeeStatus.active
                    fi.save(update_fields=["status"])
                    FeeIncludeAudit.objects.create(
                        fee_include=fi,
                        actor=actor,
                        action=FeeIncludeAuditAction.UPDATE,
                        prev_status=prev,
                        new_status=fi.status,
                        prev_batch_id=batch.id,
                        new_batch_id=batch.id,
                        prev_class_id=academic_class.id,
                        new_class_id=academic_class.id,
                    )
                else:
                    # still write a CREATE audit? Usually no.
                    pass
            else:
                created_includes.append(fi)
                FeeIncludeAudit.objects.create(
                    fee_include=fi,
                    actor=actor,
                    action=FeeIncludeAuditAction.CREATE,
                    prev_status="",
                    new_status=fi.status,
                    prev_batch_id=None,
                    new_batch_id=batch.id,
                    prev_class_id=None,
                    new_class_id=academic_class.id,
                )

        # 4) StudentFeeWallet upsert for this batch+class scope
        wallet, _ = StudentFeeWallet.objects.get_or_create(
            student=student,
            batch=batch,
            academic_class=academic_class,
            defaults={
                "total_payable": Decimal("0.00"),
                "total_paid": Decimal("0.00"),
                "total_discount": Decimal("0.00"),
                "total_scholarship": Decimal("0.00"),
                "total_due": Decimal("0.00"),
            },
        )

        wallet.total_payable = total_payable
        wallet.total_discount = discount
        wallet.total_scholarship = scholarship

        # paid stays as-is (0 for new wallets, or keep existing payments if any)
        if wallet.total_paid is None:
            wallet.total_paid = Decimal("0.00")

        wallet.total_due = (wallet.total_payable - wallet.total_discount - wallet.total_scholarship) - wallet.total_paid
        if wallet.total_due < 0:
            wallet.total_due = Decimal("0.00")

        wallet.save(update_fields=["total_payable", "total_discount", "total_scholarship", "total_paid", "total_due", "updated_at"])

        return {
            "enrollment": enrollment,
            "wallet": wallet,
            "fee_includes_created": created_includes,
        }
