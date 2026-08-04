from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.constants import Currency

MONEY_ZERO = Decimal("0.00")


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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    group = models.CharField(max_length=20, choices=FeeHeadGroup.choices, default=FeeHeadGroup.OTHER)
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
    fee_head = models.ForeignKey("fees.FeeHead", on_delete=models.PROTECT, related_name="structures")
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="fee_structures")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.NPR)
    period = models.CharField(max_length=20, choices=FeePeriod.choices, default=FeePeriod.ANNUAL)
    status = models.CharField(max_length=20, choices=FeeStatus.choices, default=FeeStatus.active, db_index=True)
    upgrade_impact = models.BooleanField(default=False)
    scope = models.CharField(
        max_length=20,
        choices=FeeScope.choices,
        default=FeeScope.GLOBAL,
        db_index=True,
        help_text=(
            "GLOBAL: all students. BATCH: one batch. CLASS: one class across batches. "
            "BATCH_CLASS: one class inside one batch."
        ),
    )
    tax_included = models.BooleanField(default=False)
    batch = models.ForeignKey(
        "batch.AcademicBatch", on_delete=models.CASCADE, related_name="fee_structures", null=True, blank=True
    )
    academic_class = models.ForeignKey(
        "academics.AcademicClass", on_delete=models.CASCADE, related_name="fee_structures", null=True, blank=True
    )
    # MySQL unique constraints allow multiple NULLs. This normalized key closes that gap.
    definition_key = models.CharField(max_length=255, null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "scope", "status"]),
            models.Index(fields=["school", "batch", "academic_class"]),
        ]

    def build_definition_key(self) -> str:
        return ":".join(
            [
                str(self.school_id or ""),
                str(self.fee_head_id or ""),
                str(self.period or ""),
                str(self.scope or ""),
                str(self.batch_id or "-"),
                str(self.academic_class_id or "-"),
                str(self.status or ""),
            ]
        )

    def clean(self):
        if self.fee_head_id and not self.fee_head.is_active:
            raise ValidationError({"fee_head": ["This fee head is inactive and cannot be used."]})
        if self.amount is not None and self.amount < MONEY_ZERO:
            raise ValidationError({"amount": ["Amount must be greater than or equal to zero."]})
        if self.batch_id and self.batch.school_id != self.school_id:
            raise ValidationError({"batch": ["Batch does not belong to this school."]})
        if self.academic_class_id and self.academic_class.batch_id:
            class_school_id = self.academic_class.batch.school_id
            if self.school_id and class_school_id != self.school_id:
                raise ValidationError({"academic_class": ["Class does not belong to this school."]})

        if self.scope == FeeScope.GLOBAL:
            if self.batch_id or self.academic_class_id:
                raise ValidationError({"scope": ["GLOBAL cannot have batch or class set."]})
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
            if self.academic_class.batch_id and self.academic_class.batch_id != self.batch_id:
                raise ValidationError({"academic_class": ["Class must belong to the selected batch."]})
        else:
            raise ValidationError({"scope": ["Invalid scope value."]})

        self.definition_key = self.build_definition_key()

    def save(self, *args, **kwargs):
        self.definition_key = self.build_definition_key()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.school.code} | {self.fee_head.code} | {self.scope} | {self.period} | {self.amount} {self.currency}"


class FeeInclude(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fees = models.ForeignKey("fees.FeeStructure", on_delete=models.CASCADE, related_name="included_in")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="fee_includes")
    batch = models.ForeignKey("batch.AcademicBatch", on_delete=models.CASCADE, related_name="fee_includes")
    classroom = models.ForeignKey("academics.AcademicClass", on_delete=models.CASCADE, related_name="fee_includes")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=FeeStatus.choices, default=FeeStatus.active, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fees", "user", "batch", "classroom"],
                condition=~Q(status=FeeStatus.deleted),
                name="uq_fee_include_definition_not_deleted",
            )
        ]

    def __str__(self):
        return f"{self.user} included in {self.fees} for {self.batch} - {self.classroom}"


class StudentFeeWallet(models.Model):
    """Rebuildable summary only. Never use this table as the financial source of truth."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="fee_wallets")
    batch = models.ForeignKey("batch.AcademicBatch", on_delete=models.CASCADE, related_name="fee_wallets")
    academic_class = models.ForeignKey("academics.AcademicClass", on_delete=models.CASCADE, related_name="fee_wallets")
    total_payable = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    total_paid = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    total_discount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    total_scholarship = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    total_due = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    advance_balance = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.NPR)
    last_reconciled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "batch", "academic_class"], name="uq_student_wallet_scope")
        ]
        indexes = [models.Index(fields=["student", "batch", "academic_class"])]

    def __str__(self):
        return f"Wallet({self.student_id} {self.batch_id} {self.academic_class_id})"


class FeeIncludeAuditAction(models.TextChoices):
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"
    UNDO = "undo", "Undo"


class FeeIncludeAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fee_include = models.ForeignKey("fees.FeeInclude", on_delete=models.CASCADE, related_name="audits")
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="fee_include_audits"
    )
    action = models.CharField(max_length=10, choices=FeeIncludeAuditAction.choices)
    prev_status = models.CharField(max_length=20, blank=True, default="")
    new_status = models.CharField(max_length=20, blank=True, default="")
    prev_batch_id = models.IntegerField(null=True, blank=True)
    new_batch_id = models.IntegerField(null=True, blank=True)
    prev_class_id = models.UUIDField(null=True, blank=True)
    new_class_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["fee_include", "created_at"])]


class FeeConfiguration(models.Model):
    school = models.OneToOneField("schools.School", on_delete=models.CASCADE, related_name="fee_configuration")
    invoice_prefix = models.CharField(max_length=12, default="INV")
    receipt_prefix = models.CharField(max_length=12, default="RCPT")
    default_due_days = models.PositiveSmallIntegerField(default=10)
    allow_backdated_payments = models.BooleanField(default=True)
    auto_apply_advance = models.BooleanField(default=True)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.NPR)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DocumentSequenceKind(models.TextChoices):
    INVOICE = "INVOICE", "Invoice"
    RECEIPT = "RECEIPT", "Receipt"


class FeeDocumentSequence(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="fee_document_sequences")
    kind = models.CharField(max_length=20, choices=DocumentSequenceKind.choices)
    year = models.PositiveSmallIntegerField()
    last_number = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "kind", "year"], name="uq_fee_document_sequence")]




class ImmutableFinancialQuerySet(models.QuerySet):
    def delete(self):
        raise ValidationError("Posted financial records cannot be deleted. Use reversal or void workflows.")


class ImmutableFinancialManager(models.Manager.from_queryset(ImmutableFinancialQuerySet)):
    pass


class ImmutableFinancialRecord(models.Model):
    objects = ImmutableFinancialManager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted financial records cannot be deleted. Use reversal or void workflows.")

class ConcessionKind(models.TextChoices):
    DISCOUNT = "DISCOUNT", "Discount"
    SCHOLARSHIP = "SCHOLARSHIP", "Scholarship"


class ConcessionCalculation(models.TextChoices):
    FIXED = "FIXED", "Fixed amount"
    PERCENTAGE = "PERCENTAGE", "Percentage"


class ConcessionFrequency(models.TextChoices):
    PER_INVOICE = "PER_INVOICE", "Per invoice"
    ONE_TIME = "ONE_TIME", "One time"


class ConcessionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVOKED = "REVOKED", "Revoked"


class StudentFeeConcession(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="fee_concessions")
    student = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="fee_concessions")
    batch = models.ForeignKey("batch.AcademicBatch", on_delete=models.PROTECT, related_name="fee_concessions")
    academic_class = models.ForeignKey(
        "academics.AcademicClass", on_delete=models.PROTECT, related_name="fee_concessions"
    )
    fee_head = models.ForeignKey(
        "fees.FeeHead", on_delete=models.PROTECT, null=True, blank=True, related_name="student_concessions"
    )
    kind = models.CharField(max_length=20, choices=ConcessionKind.choices)
    calculation = models.CharField(max_length=20, choices=ConcessionCalculation.choices)
    value = models.DecimalField(max_digits=14, decimal_places=2)
    frequency = models.CharField(
        max_length=20, choices=ConcessionFrequency.choices, default=ConcessionFrequency.PER_INVOICE
    )
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    maximum_total_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=ConcessionStatus.choices, default=ConcessionStatus.ACTIVE)
    approved_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_fee_concessions"
    )
    revoked_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="revoked_fee_concessions"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "student", "batch", "academic_class", "status"], name="fees_concession_scope_idx"),
            models.Index(fields=["valid_from", "valid_until"], name="fees_concession_valid_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="ck_fee_concession_value_gt_zero"),
            models.CheckConstraint(
                condition=Q(calculation=ConcessionCalculation.FIXED) | Q(value__lte=Decimal("100.00")),
                name="ck_fee_concession_percentage_lte_100",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F("valid_from")),
                name="ck_fee_concession_date_order",
            ),
            models.CheckConstraint(
                condition=Q(maximum_total_amount__isnull=True) | Q(maximum_total_amount__gt=0),
                name="ck_fee_concession_max_gt_zero",
            ),
        ]

    def clean(self):
        if self.batch_id and self.batch.school_id != self.school_id:
            raise ValidationError({"batch": ["Batch does not belong to this school."]})
        if self.academic_class_id and self.academic_class.batch_id != self.batch_id:
            raise ValidationError({"academic_class": ["Class does not belong to this batch."]})
        profile_school_id = getattr(getattr(self.student, "profile", None), "school_id", None)
        if profile_school_id and profile_school_id != self.school_id:
            raise ValidationError({"student": ["Student does not belong to this school."]})
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": ["valid_until must be on or after valid_from."]})
        if self.calculation == ConcessionCalculation.PERCENTAGE and self.value > Decimal("100.00"):
            raise ValidationError({"value": ["Percentage cannot exceed 100."]})
        if self.maximum_total_amount is not None and self.maximum_total_amount <= MONEY_ZERO:
            raise ValidationError({"maximum_total_amount": ["Maximum amount must be greater than zero."]})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class InvoiceStatus(models.TextChoices):
    ISSUED = "ISSUED", "Issued"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"
    VOID = "VOID", "Void"


class FeeInvoice(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="fee_invoices")
    enrollment = models.ForeignKey(
        "academics.StudentEnrollments", on_delete=models.PROTECT, related_name="fee_invoices"
    )
    student = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="fee_invoices")
    batch = models.ForeignKey("batch.AcademicBatch", on_delete=models.PROTECT, related_name="fee_invoices")
    academic_class = models.ForeignKey(
        "academics.AcademicClass", on_delete=models.PROTECT, related_name="fee_invoices"
    )
    invoice_number = models.CharField(max_length=64, unique=True)
    billing_key = models.CharField(max_length=255, unique=True, editable=False)
    period_start = models.DateField()
    period_end = models.DateField()
    invoice_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.ISSUED)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.NPR)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    scholarship_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    advance_applied = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    due_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    opening_due_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    account_due_at_issue = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    notes = models.CharField(max_length=500, blank=True, default="")
    idempotency_key = models.CharField(max_length=100, null=True, blank=True)
    generated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_fee_invoices"
    )
    voided_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="voided_fee_invoices"
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["school", "student", "period_start", "period_end"],
                name="fee_inv_student_period",
            ),
            models.Index(
                fields=["school", "status", "due_date"],
                name="fee_inv_status_due",
            ),
            models.Index(
                fields=["enrollment", "created_at"],
                name="fee_inv_enroll_created",
            ),
        ]

    @staticmethod
    def make_billing_key(enrollment_id, period_start, period_end) -> str:
        return f"{enrollment_id}:{period_start.isoformat()}:{period_end.isoformat()}"

    def clean(self):
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": ["period_end must be on or after period_start."]})
        if self.due_date < self.invoice_date:
            raise ValidationError({"due_date": ["due_date cannot be before invoice_date."]})
        if self.enrollment_id:
            if self.enrollment.student_id != self.student_id:
                raise ValidationError({"student": ["Student does not match the enrollment."]})
            if self.enrollment.batch_id != self.batch_id:
                raise ValidationError({"batch": ["Batch does not match the enrollment."]})
            if self.enrollment.academic_class_id != self.academic_class_id:
                raise ValidationError({"academic_class": ["Class does not match the enrollment."]})
        expected = self.make_billing_key(self.enrollment_id, self.period_start, self.period_end)
        void_key = f"{expected}:VOID:{self.id}"
        if self.status == InvoiceStatus.VOID:
            if self.billing_key and self.billing_key not in {expected, void_key}:
                raise ValidationError({"billing_key": ["Invalid voided-invoice billing key."]})
            self.billing_key = self.billing_key or void_key
        else:
            if self.billing_key and self.billing_key != expected:
                raise ValidationError({"billing_key": ["Invalid billing key."]})
            self.billing_key = expected

    def __str__(self):
        return self.invoice_number


class FeeInvoiceLine(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey("fees.FeeInvoice", on_delete=models.CASCADE, related_name="lines")
    fee_structure = models.ForeignKey(
        "fees.FeeStructure", on_delete=models.PROTECT, related_name="invoice_lines"
    )
    fee_head = models.ForeignKey("fees.FeeHead", on_delete=models.PROTECT, related_name="invoice_lines")
    fee_head_code = models.CharField(max_length=50)
    fee_head_name = models.CharField(max_length=120)
    fee_period = models.CharField(max_length=20, choices=FeePeriod.choices)
    description = models.CharField(max_length=255, blank=True, default="")
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))
    unit_amount = models.DecimalField(max_digits=14, decimal_places=2)
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    scholarship_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2)
    source_start = models.DateField()
    source_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fee_head_name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["invoice", "fee_structure"], name="uq_invoice_fee_structure_line"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="ck_invoice_line_quantity_gt_zero"),
            models.CheckConstraint(condition=Q(unit_amount__gte=0), name="ck_invoice_line_unit_nonnegative"),
            models.CheckConstraint(condition=Q(gross_amount__gte=0), name="ck_invoice_line_gross_nonnegative"),
            models.CheckConstraint(condition=Q(net_amount__gte=0), name="ck_invoice_line_net_nonnegative"),
            models.CheckConstraint(
                condition=Q(net_amount=models.F("gross_amount") - models.F("discount_amount") - models.F("scholarship_amount")),
                name="ck_invoice_line_net_equation",
            ),
        ]


class FeeInvoiceAdjustment(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_line = models.ForeignKey(
        "fees.FeeInvoiceLine", on_delete=models.CASCADE, related_name="adjustments"
    )
    concession = models.ForeignKey(
        "fees.StudentFeeConcession", on_delete=models.PROTECT, related_name="invoice_adjustments"
    )
    kind = models.CharField(max_length=20, choices=ConcessionKind.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["invoice_line", "concession"], name="uq_line_concession_adjustment"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_invoice_adjustment_gt_zero"),
        ]


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
    CHEQUE = "CHEQUE", "Cheque"
    CARD = "CARD", "Card"
    ESEWA = "ESEWA", "eSewa"
    KHALTI = "KHALTI", "Khalti"
    FONEPAY = "FONEPAY", "Fonepay"
    OTHER = "OTHER", "Other"


class PaymentStatus(models.TextChoices):
    POSTED = "POSTED", "Posted"
    REVERSED = "REVERSED", "Reversed"


class FeePayment(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="fee_payments")
    enrollment = models.ForeignKey(
        "academics.StudentEnrollments", on_delete=models.PROTECT, related_name="fee_payments"
    )
    student = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="fee_payments")
    batch = models.ForeignKey("batch.AcademicBatch", on_delete=models.PROTECT, related_name="fee_payments")
    academic_class = models.ForeignKey(
        "academics.AcademicClass", on_delete=models.PROTECT, related_name="fee_payments"
    )
    receipt_number = models.CharField(max_length=64, unique=True)
    paid_at = models.DateTimeField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.NPR)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices)
    external_reference = models.CharField(max_length=100, blank=True, default="")
    notes = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.POSTED)
    idempotency_key = models.CharField(max_length=100)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    account_gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    account_discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    account_scholarship_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    account_net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    account_paid_after = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    before_payment_due = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    after_payment_due = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    advance_created = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    advance_balance_after = models.DecimalField(max_digits=14, decimal_places=2, default=MONEY_ZERO)
    received_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="received_fee_payments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["school", "student", "paid_at"],
                name="fee_pay_student_paid",
            ),
            models.Index(
                fields=["school", "status", "created_at"],
                name="fee_pay_status_created",
            ),
        ]

    def clean(self):
        if self.enrollment_id:
            if self.enrollment.student_id != self.student_id:
                raise ValidationError({"student": ["Student does not match the enrollment."]})
            if self.enrollment.batch_id != self.batch_id:
                raise ValidationError({"batch": ["Batch does not match the enrollment."]})
            if self.enrollment.academic_class_id != self.academic_class_id:
                raise ValidationError({"academic_class": ["Class does not match the enrollment."]})

    def __str__(self):
        return self.receipt_number


class AllocationStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVERSED = "REVERSED", "Reversed"


class FeePaymentAllocation(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey("fees.FeePayment", on_delete=models.PROTECT, related_name="allocations")
    invoice = models.ForeignKey("fees.FeeInvoice", on_delete=models.PROTECT, related_name="payment_allocations")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=AllocationStatus.choices, default=AllocationStatus.ACTIVE)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="reversed_payment_allocations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payment", "invoice"], name="uq_payment_invoice_allocation"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_payment_allocation_gt_zero"),
        ]


class AdvanceCreditStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CONSUMED = "CONSUMED", "Consumed"
    REVERSED = "REVERSED", "Reversed"


class FeeAdvanceCredit(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="fee_advance_credits")
    enrollment = models.ForeignKey(
        "academics.StudentEnrollments", on_delete=models.PROTECT, related_name="fee_advance_credits"
    )
    student = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="fee_advance_credits")
    payment = models.OneToOneField("fees.FeePayment", on_delete=models.PROTECT, related_name="advance_credit")
    original_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.NPR)
    available_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=AdvanceCreditStatus.choices, default=AdvanceCreditStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["school", "student", "status", "created_at"],
                name="fee_adv_student_status",
            )
        ]


class AdvanceApplicationStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVERSED = "REVERSED", "Reversed"


class FeeAdvanceApplication(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credit = models.ForeignKey("fees.FeeAdvanceCredit", on_delete=models.PROTECT, related_name="applications")
    invoice = models.ForeignKey("fees.FeeInvoice", on_delete=models.PROTECT, related_name="advance_applications")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=AdvanceApplicationStatus.choices, default=AdvanceApplicationStatus.ACTIVE
    )
    applied_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="applied_fee_advances"
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="reversed_fee_advances"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["credit", "invoice"], name="uq_advance_credit_invoice"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_advance_application_gt_zero"),
        ]


class FeePaymentReversal(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField("fees.FeePayment", on_delete=models.PROTECT, related_name="reversal")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=255)
    reversed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="fee_payment_reversals"
    )
    reversed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="ck_payment_reversal_gt_zero")]


class FeeAuditEvent(ImmutableFinancialRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="fee_audit_events")
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="fee_audit_events"
    )
    event_type = models.CharField(max_length=60, db_index=True)
    entity_type = models.CharField(max_length=40, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["school", "entity_type", "entity_id", "created_at"], name="fees_audit_entity_idx")]
        ordering = ["-created_at"]
