# fees/models.py
from __future__ import annotations

import uuid
from django.db import models
from common.constants import Currency
from django.core.exceptions import ValidationError

# ---------------------------
# Choices / Enums
# ---------------------------

class FeeHeadGroup(models.TextChoices):
    ONE_TIME = "ONE_TIME", "One-time"
    TUITION = "TUITION", "Tuition"
    EXAM = "EXAM", "Exam"
    TRANSPORT = "TRANSPORT", "Transport"
    HOSTEL = "HOSTEL", "Hostel"
    MATERIAL = "MATERIAL", "Materials"
    UNIFORM = "UNIFORM", "Uniform"
    DOCUMENT = "DOCUMENT", "Documents"
    CERTIFICATE = "CERTIFICATE", "Certificate"
    PENALTY = "PENALTY", "Penalty"
    SPORTS = "SPORTS", "Sports"
    ECA = "ECA", "ECA"
    OTHER = "OTHER", "Other"

class FeePeriod(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly"
    QUARTERLY = "QUARTERLY", "Quarterly"
    SEMESTER = "SEMESTER", "Semester"
    ANNUAL = "ANNUAL", "Annual"
    OTHER = "OTHER", "Other"
    ONE_TIME = "ONE_TIME", "One Time"

class FeeStatus(models.TextChoices):
    active = "active", "Active"
    inactive = "inactive", "Inactive"
    archived = "archived", "Archived"
    deleted = "deleted", "Deleted"
    expired = "expired", "Expired"

class FeeScope(models.TextChoices):
    GLOBAL = "GLOBAL", "Global"
    BATCH = "BATCH", "Batch"
    CLASS = "CLASS", "Class"
    BATCH_CLASS = "BATCH_CLASS", "Batch + Class"

class FeeHead(models.Model):
    """
    A "fee category/head" you can CRUD from admin:
    Tuition Fee, Admission Fee, ID Card, Uniform, Late Fine, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=50, unique=True)  # e.g. TUITION, ADMISSION

    group = models.CharField(
        max_length=20,
        choices=FeeHeadGroup.choices,
        default=FeeHeadGroup.OTHER,
    )
    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

class FeeStructure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    fee_head = models.ForeignKey(
        "fees.FeeHead",
        on_delete=models.PROTECT,
        related_name="structures",
    )

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="fee_structures",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    currency = models.CharField(
        max_length=10,
        choices=Currency.choices,
        default=Currency.NPR,
    )

    period = models.CharField(
        max_length=20,
        choices=FeePeriod.choices,  # or FeePeriod.choices if in same file
        default=FeePeriod.ANNUAL,
    )

    status = models.CharField(
        max_length=20,
        choices=FeeStatus.choices,  # or FeeStatus.choices
        default=FeeStatus.active,
        db_index=True,
    )

    upgrade_impact = models.BooleanField(default=False)

    scope = models.CharField(
        max_length=20,
        choices=FeeScope.choices,  # or FeeScope.choices
        default=FeeScope.GLOBAL,
        db_index=True,
        help_text=(
            "GLOBAL: applies to all students (no batch/class). "
            "BATCH: applies to all students in one batch (batch required). "
            "CLASS: applies to one class across batches (class required). "
            "BATCH_CLASS: applies to a specific batch+class (both required)."
        ),
    )
    tax_included = models.BooleanField(default=False)
    # Optional depending on scope
    batch = models.ForeignKey(
        "batch.AcademicBatch",
        on_delete=models.CASCADE,
        related_name="fee_structures",
        null=True,
        blank=True,
    )

    academic_class = models.ForeignKey(
        "academics.AcademicClass",
        on_delete=models.CASCADE,
        related_name="fee_structures",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "scope", "status"]),
            models.Index(fields=["school", "batch", "academic_class"]),
        ]
        constraints = [
            # Prevent duplicates for same definition (especially active ones)
            models.UniqueConstraint(
                fields=["school", "fee_head", "period", "scope", "batch", "academic_class", "status"],
                name="uq_fee_structure_definition",
            ),
        ]

    def clean(self):
        # FeeHead must be active
        if self.fee_head_id and not self.fee_head.is_active:
            raise ValidationError({"fee_head": ["This fee head is inactive and cannot be used."]})

        # Batch must belong to the same school
        if self.batch_id and self.batch.school_id != self.school_id:
            raise ValidationError({"batch": ["Batch does not belong to this school."]})

        # Scope enforcement
        from .models import FeeScope  # adjust import if needed

        if self.scope == FeeScope.GLOBAL:
            if self.batch_id or self.academic_class_id:
                raise ValidationError({"scope": ["GLOBAL cannot have batch/class set."]})

        elif self.scope == FeeScope.BATCH:
            if not self.batch_id:
                raise ValidationError({"batch": ["Batch is required for BATCH scope."]})
            if self.academic_class_id:
                raise ValidationError({"academic_class": ["Class must be empty for BATCH scope."]})

        elif self.scope == FeeScope.CLASS:
            if not self.academic_class_id:
                raise ValidationError({"academic_class": ["Class is required for CLASS scope."]})
            if self.batch_id:
                raise ValidationError({"batch": ["Batch must be empty for CLASS scope."]})

        elif self.scope == FeeScope.BATCH_CLASS:
            if not self.batch_id:
                raise ValidationError({"batch": ["Batch is required for BATCH_CLASS scope."]})
            if not self.academic_class_id:
                raise ValidationError({"academic_class": ["Class is required for BATCH_CLASS scope."]})

            # Ensure class belongs to the same batch (since your AcademicClass has batch FK)
            if self.academic_class.batch_id and self.academic_class.batch_id != self.batch_id:
                raise ValidationError(
                    {"academic_class": ["Class must belong to the selected batch for BATCH_CLASS scope."]}
                )

        else:
            raise ValidationError({"scope": ["Invalid scope value."]})

        # Amount sanity
        if self.amount is not None and self.amount < 0:
            raise ValidationError({"amount": ["Amount must be >= 0."]})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.school.code} | {self.fee_head.code} | {self.scope} | {self.period} | {self.amount} {self.currency}"