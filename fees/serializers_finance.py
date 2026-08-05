from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from academics.models import (
    AcademicClass,
    Section,
    StudentEnrollments,
)
from accounts.models import User
from batch.models import AcademicBatch
from fees.models import (
    ConcessionStatus,
    FeeAdvanceApplication,
    FeeAdvanceCredit,
    FeeConfiguration,
    FeeInvoice,
    FeeInvoiceAdjustment,
    FeeInvoiceLine,
    FeePayment,
    FeePaymentAllocation,
    PaymentMethod,
    StudentFeeConcession,
    StudentFeeWallet,
)
from utils.get_school_id_by_token import get_school_for_user


class UserFeeMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "registration_no",
            "full_name",
            "phone",
        ]

    def get_full_name(self, obj):
        return " ".join(
            part
            for part in [
                obj.first_name,
                obj.middle_name,
                obj.last_name,
            ]
            if part
        ).strip()


class EnrollmentFeeMiniSerializer(
    serializers.ModelSerializer
):
    student_detail = UserFeeMiniSerializer(
        source="student",
        read_only=True,
    )
    batch_name = serializers.CharField(
        source="batch.name",
        read_only=True,
    )
    class_name = serializers.CharField(
        source="academic_class.name",
        read_only=True,
    )
    section_name = serializers.CharField(
        source="section.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = StudentEnrollments
        fields = [
            "id",
            "student",
            "student_detail",
            "batch",
            "batch_name",
            "academic_class",
            "class_name",
            "section",
            "section_name",
            "status",
        ]


class FeeInvoiceAdjustmentReadSerializer(
    serializers.ModelSerializer
):
    concession_reason = serializers.CharField(
        source="concession.reason",
        read_only=True,
    )

    class Meta:
        model = FeeInvoiceAdjustment
        fields = [
            "id",
            "concession",
            "kind",
            "amount",
            "reason",
            "concession_reason",
            "created_at",
        ]


class FeeInvoiceLineReadSerializer(
    serializers.ModelSerializer
):
    adjustments = (
        FeeInvoiceAdjustmentReadSerializer(
            many=True,
            read_only=True,
        )
    )

    class Meta:
        model = FeeInvoiceLine
        fields = [
            "id",
            "fee_structure",
            "fee_head",
            "fee_head_code",
            "fee_head_name",
            "fee_period",
            "description",
            "quantity",
            "unit_amount",
            "gross_amount",
            "discount_amount",
            "scholarship_amount",
            "net_amount",
            "source_start",
            "source_end",
            "adjustments",
        ]


class FeeInvoiceReadSerializer(
    serializers.ModelSerializer
):
    student_detail = UserFeeMiniSerializer(
        source="student",
        read_only=True,
    )
    batch_name = serializers.CharField(
        source="batch.name",
        read_only=True,
    )
    class_name = serializers.CharField(
        source="academic_class.name",
        read_only=True,
    )
    section_id = serializers.UUIDField(
        source="enrollment.section_id",
        read_only=True,
        allow_null=True,
    )
    section_name = serializers.CharField(
        source="enrollment.section.name",
        read_only=True,
        allow_null=True,
    )
    lines = FeeInvoiceLineReadSerializer(
        many=True,
        read_only=True,
    )
    generated_by_name = (
        serializers.SerializerMethodField()
    )

    def get_generated_by_name(self, obj):
        if not obj.generated_by:
            return None

        return str(obj.generated_by)

    class Meta:
        model = FeeInvoice
        fields = [
            "id",
            "invoice_number",
            "student",
            "student_detail",
            "enrollment",
            "batch",
            "batch_name",
            "academic_class",
            "class_name",
            "section_id",
            "section_name",
            "period_start",
            "period_end",
            "invoice_date",
            "due_date",
            "status",
            "currency",
            "subtotal",
            "discount_amount",
            "scholarship_amount",
            "total_amount",
            "paid_amount",
            "advance_applied",
            "due_amount",
            "opening_due_amount",
            "account_due_at_issue",
            "notes",
            "generated_by",
            "generated_by_name",
            "voided_by",
            "voided_at",
            "void_reason",
            "created_at",
            "lines",
        ]


class InvoiceGenerateSerializer(
    serializers.Serializer
):
    enrollment_id = serializers.UUIDField()

    period_start = serializers.DateField()
    period_end = serializers.DateField()

    invoice_date = serializers.DateField(
        required=False,
    )
    due_date = serializers.DateField(
        required=False,
    )

    apply_advance = serializers.BooleanField(
        required=False,
        allow_null=True,
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default="",
    )

    idempotency_key = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=100,
    )

    def validate(self, attrs):
        request = self.context["request"]
        school = get_school_for_user(
            request.user
        )

        enrollment = (
            StudentEnrollments.objects
            .select_related(
                "batch__school",
                "academic_class",
                "section",
            )
            .filter(
                id=attrs["enrollment_id"],
                batch__school=school,
            )
            .first()
        )

        if enrollment is None:
            raise serializers.ValidationError({
                "enrollment_id": [
                    "Enrollment not found in your school."
                ]
            })

        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError({
                "period_end": [
                    (
                        "period_end must be on or "
                        "after period_start."
                    )
                ]
            })

        invoice_date = (
            attrs.get("invoice_date")
            or timezone.localdate()
        )
        due_date = attrs.get("due_date")

        if (
            due_date is not None
            and due_date < invoice_date
        ):
            raise serializers.ValidationError({
                "due_date": [
                    (
                        "due_date cannot be before "
                        "invoice_date."
                    )
                ]
            })

        attrs["enrollment"] = enrollment

        return attrs


class BulkInvoiceGenerateSerializer(
    serializers.Serializer
):
    """
    Generates invoices using exactly one selection method:

    1. student_ids
    2. enrollment_ids
    3. batch_id, optionally narrowed by class and section

    When section_id is null or omitted, all sections and students
    without a section are included within the selected batch/class.
    """

    student_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=False,
    )

    enrollment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=False,
    )

    batch_id = serializers.IntegerField(
        required=False,
    )

    academic_class_id = serializers.UUIDField(
        required=False,
    )

    section_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    period_start = serializers.DateField()
    period_end = serializers.DateField()

    invoice_date = serializers.DateField(
        required=False,
    )

    due_date = serializers.DateField(
        required=False,
    )

    apply_advance = serializers.BooleanField(
        required=False,
        allow_null=True,
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default="",
    )

    def validate(self, attrs):
        period_start = attrs["period_start"]
        period_end = attrs["period_end"]

        if period_end < period_start:
            raise serializers.ValidationError({
                "period_end": [
                    (
                        "period_end must be on or "
                        "after period_start."
                    )
                ]
            })

        for field_name in (
            "student_ids",
            "enrollment_ids",
        ):
            values = attrs.get(field_name) or []

            if len(values) != len(set(values)):
                raise serializers.ValidationError({
                    field_name: [
                        "Duplicate IDs are not allowed."
                    ]
                })

        student_ids = attrs.get("student_ids")
        enrollment_ids = attrs.get(
            "enrollment_ids"
        )
        batch_id = attrs.get("batch_id")

        selection_count = sum([
            bool(student_ids),
            bool(enrollment_ids),
            batch_id is not None,
        ])

        if selection_count != 1:
            raise serializers.ValidationError({
                "selection": [
                    (
                        "Use exactly one selection method: "
                        "student_ids, enrollment_ids, "
                        "or batch_id."
                    )
                ]
            })

        academic_class_id = attrs.get(
            "academic_class_id"
        )
        section_id = attrs.get("section_id")

        if (
            academic_class_id is not None
            and batch_id is None
        ):
            raise serializers.ValidationError({
                "academic_class_id": [
                    (
                        "academic_class_id requires "
                        "batch_id."
                    )
                ]
            })

        if (
            section_id is not None
            and academic_class_id is None
        ):
            raise serializers.ValidationError({
                "section_id": [
                    (
                        "section_id requires "
                        "academic_class_id."
                    )
                ]
            })

        request = self.context["request"]
        school = get_school_for_user(
            request.user
        )

        if batch_id is not None:
            batch_exists = (
                AcademicBatch.objects.filter(
                    id=batch_id,
                    school=school,
                ).exists()
            )

            if not batch_exists:
                raise serializers.ValidationError({
                    "batch_id": [
                        "Batch not found in your school."
                    ]
                })

        if academic_class_id is not None:
            class_exists = (
                AcademicClass.objects.filter(
                    id=academic_class_id,
                    batch_id=batch_id,
                    batch__school=school,
                ).exists()
            )

            if not class_exists:
                raise serializers.ValidationError({
                    "academic_class_id": [
                        (
                            "Class not found in the "
                            "selected batch."
                        )
                    ]
                })

        if section_id is not None:
            section_exists = (
                Section.objects.filter(
                    id=section_id,
                    academic_class_id=(
                        academic_class_id
                    ),
                    academic_class__batch_id=(
                        batch_id
                    ),
                    academic_class__batch__school=(
                        school
                    ),
                ).exists()
            )

            if not section_exists:
                raise serializers.ValidationError({
                    "section_id": [
                        (
                            "Section not found in the "
                            "selected class."
                        )
                    ]
                })

        invoice_date = (
            attrs.get("invoice_date")
            or timezone.localdate()
        )
        due_date = attrs.get("due_date")

        if (
            due_date is not None
            and due_date < invoice_date
        ):
            raise serializers.ValidationError({
                "due_date": [
                    (
                        "due_date cannot be before "
                        "invoice_date."
                    )
                ]
            })

        return attrs


class InvoiceIdListSerializer(
    serializers.Serializer
):
    invoice_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )

    def validate_invoice_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate invoice IDs are not allowed."
            )

        return value


class FinancialReasonSerializer(
    serializers.Serializer
):
    reason = serializers.CharField(
        max_length=255,
        allow_blank=False,
        trim_whitespace=True,
    )


class FeePaymentAllocationReadSerializer(
    serializers.ModelSerializer
):
    invoice_number = serializers.CharField(
        source="invoice.invoice_number",
        read_only=True,
    )

    invoice_due_after = (
        serializers.DecimalField(
            source="invoice.due_amount",
            max_digits=14,
            decimal_places=2,
            read_only=True,
        )
    )

    class Meta:
        model = FeePaymentAllocation
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "amount",
            "status",
            "invoice_due_after",
            "created_at",
        ]


class FeePaymentReadSerializer(
    serializers.ModelSerializer
):
    student_detail = UserFeeMiniSerializer(
        source="student",
        read_only=True,
    )

    batch_name = serializers.CharField(
        source="batch.name",
        read_only=True,
    )

    class_name = serializers.CharField(
        source="academic_class.name",
        read_only=True,
    )

    section_id = serializers.UUIDField(
        source="enrollment.section_id",
        read_only=True,
        allow_null=True,
    )

    section_name = serializers.CharField(
        source="enrollment.section.name",
        read_only=True,
        allow_null=True,
    )

    received_by_name = (
        serializers.SerializerMethodField()
    )

    allocations = (
        FeePaymentAllocationReadSerializer(
            many=True,
            read_only=True,
        )
    )

    def get_received_by_name(self, obj):
        if not obj.received_by:
            return None

        return str(obj.received_by)

    class Meta:
        model = FeePayment
        fields = [
            "id",
            "receipt_number",
            "student",
            "student_detail",
            "enrollment",
            "batch",
            "batch_name",
            "academic_class",
            "class_name",
            "section_id",
            "section_name",
            "paid_at",
            "amount",
            "currency",
            "payment_method",
            "external_reference",
            "notes",
            "status",
            "account_gross_amount",
            "account_discount_amount",
            "account_scholarship_amount",
            "account_net_amount",
            "account_paid_after",
            "before_payment_due",
            "after_payment_due",
            "advance_created",
            "advance_balance_after",
            "received_by",
            "received_by_name",
            "created_at",
            "allocations",
        ]


class FeePaymentCreateSerializer(
    serializers.Serializer
):
    enrollment_id = serializers.UUIDField()

    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    paid_at = serializers.DateTimeField(
        default=timezone.now,
    )

    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
    )

    invoice_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=False,
    )

    auto_allocate = serializers.BooleanField(
        default=True,
    )

    external_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        default="",
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default="",
    )

    idempotency_key = serializers.CharField(
        max_length=100,
        allow_blank=False,
    )

    def validate(self, attrs):
        request = self.context["request"]
        school = get_school_for_user(
            request.user
        )

        enrollment = (
            StudentEnrollments.objects
            .select_related(
                "batch__school",
                "academic_class",
                "section",
            )
            .filter(
                id=attrs["enrollment_id"],
                batch__school=school,
            )
            .first()
        )

        if enrollment is None:
            raise serializers.ValidationError({
                "enrollment_id": [
                    "Enrollment not found in your school."
                ]
            })

        attrs["enrollment"] = enrollment

        invoice_ids = attrs.get(
            "invoice_ids"
        ) or []

        if len(invoice_ids) != len(set(invoice_ids)):
            raise serializers.ValidationError({
                "invoice_ids": [
                    (
                        "Duplicate invoice IDs "
                        "are not allowed."
                    )
                ]
            })

        if invoice_ids:
            valid_invoice_count = (
                FeeInvoice.objects.filter(
                    id__in=invoice_ids,
                    school=school,
                    enrollment=enrollment,
                )
                .values("id")
                .distinct()
                .count()
            )

            if valid_invoice_count != len(
                set(invoice_ids)
            ):
                raise serializers.ValidationError({
                    "invoice_ids": [
                        (
                            "One or more invoices do not "
                            "belong to the selected "
                            "enrollment or school."
                        )
                    ]
                })

        if (
            not attrs.get("auto_allocate")
            and not invoice_ids
            and not (
                attrs.get("notes") or ""
            ).strip()
        ):
            raise serializers.ValidationError({
                "notes": [
                    (
                        "Explain why this payment should "
                        "be stored fully as advance credit."
                    )
                ]
            })

        if (
            attrs["payment_method"]
            != PaymentMethod.CASH
            and not (
                attrs.get("external_reference")
                or ""
            ).strip()
        ):
            raise serializers.ValidationError({
                "external_reference": [
                    (
                        "A transaction or cheque "
                        "reference is required for "
                        "non-cash payments."
                    )
                ]
            })

        return attrs


class StudentFeeConcessionSerializer(
    serializers.ModelSerializer
):
    student_detail = UserFeeMiniSerializer(
        source="student",
        read_only=True,
    )

    fee_head_name = serializers.CharField(
        source="fee_head.name",
        read_only=True,
    )

    approved_by_name = (
        serializers.SerializerMethodField()
    )

    def get_approved_by_name(self, obj):
        if not obj.approved_by:
            return None

        return str(obj.approved_by)

    class Meta:
        model = StudentFeeConcession
        fields = [
            "id",
            "student",
            "student_detail",
            "batch",
            "academic_class",
            "fee_head",
            "fee_head_name",
            "kind",
            "calculation",
            "value",
            "frequency",
            "valid_from",
            "valid_until",
            "maximum_total_amount",
            "reason",
            "status",
            "approved_by",
            "approved_by_name",
            "revoked_by",
            "revoked_at",
            "revoke_reason",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "status",
            "approved_by",
            "approved_by_name",
            "revoked_by",
            "revoked_at",
            "revoke_reason",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        school = get_school_for_user(
            request.user
        )

        instance = self.instance

        student = attrs.get(
            "student",
            instance.student if instance else None,
        )

        batch = attrs.get(
            "batch",
            instance.batch if instance else None,
        )

        academic_class = attrs.get(
            "academic_class",
            (
                instance.academic_class
                if instance
                else None
            ),
        )

        if (
            batch is None
            or batch.school_id != school.id
        ):
            raise serializers.ValidationError({
                "batch": [
                    (
                        "Batch does not belong "
                        "to your school."
                    )
                ]
            })

        if (
            academic_class is None
            or academic_class.batch_id
            != batch.id
        ):
            raise serializers.ValidationError({
                "academic_class": [
                    (
                        "Class does not belong "
                        "to this batch."
                    )
                ]
            })

        if not StudentEnrollments.objects.filter(
            student=student,
            batch=batch,
            academic_class=academic_class,
        ).exists():
            raise serializers.ValidationError({
                "student": [
                    (
                        "Student is not enrolled in "
                        "the selected batch and class."
                    )
                ]
            })

        calculation = attrs.get(
            "calculation",
            (
                instance.calculation
                if instance
                else None
            ),
        )

        value = attrs.get(
            "value",
            instance.value if instance else None,
        )

        valid_from = attrs.get(
            "valid_from",
            (
                instance.valid_from
                if instance
                else None
            ),
        )

        valid_until = attrs.get(
            "valid_until",
            (
                instance.valid_until
                if instance
                else None
            ),
        )

        maximum = attrs.get(
            "maximum_total_amount",
            (
                instance.maximum_total_amount
                if instance
                else None
            ),
        )

        if (
            calculation == "PERCENTAGE"
            and value is not None
            and value > Decimal("100.00")
        ):
            raise serializers.ValidationError({
                "value": [
                    "Percentage cannot exceed 100."
                ]
            })

        if (
            valid_until
            and valid_from
            and valid_until < valid_from
        ):
            raise serializers.ValidationError({
                "valid_until": [
                    (
                        "valid_until must be on or "
                        "after valid_from."
                    )
                ]
            })

        if (
            maximum is not None
            and maximum <= 0
        ):
            raise serializers.ValidationError({
                "maximum_total_amount": [
                    (
                        "Maximum amount must be "
                        "greater than zero."
                    )
                ]
            })

        attrs["school"] = school

        return attrs

    def create(self, validated_data):
        school = validated_data.pop("school")

        return StudentFeeConcession.objects.create(
            school=school,
            approved_by=self.context[
                "request"
            ].user,
            **validated_data,
        )

    def update(
        self,
        instance,
        validated_data,
    ):
        validated_data.pop(
            "school",
            None,
        )

        if (
            instance.status
            != ConcessionStatus.ACTIVE
        ):
            raise serializers.ValidationError({
                "status": [
                    (
                        "A revoked concession "
                        "cannot be edited."
                    )
                ]
            })

        if instance.invoice_adjustments.exists():
            raise serializers.ValidationError({
                "concession": [
                    (
                        "A concession already used on "
                        "an invoice is immutable. "
                        "Revoke it and create a new "
                        "concession."
                    )
                ]
            })

        return super().update(
            instance,
            validated_data,
        )


class FeeAdvanceApplicationReadSerializer(
    serializers.ModelSerializer
):
    invoice_number = serializers.CharField(
        source="invoice.invoice_number",
        read_only=True,
    )

    class Meta:
        model = FeeAdvanceApplication
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "amount",
            "status",
            "applied_by",
            "reversed_at",
            "reversed_by",
            "created_at",
        ]


class FeeAdvanceCreditReadSerializer(
    serializers.ModelSerializer
):
    receipt_number = serializers.CharField(
        source="payment.receipt_number",
        read_only=True,
    )

    applications = (
        FeeAdvanceApplicationReadSerializer(
            many=True,
            read_only=True,
        )
    )

    class Meta:
        model = FeeAdvanceCredit
        fields = [
            "id",
            "student",
            "enrollment",
            "payment",
            "receipt_number",
            "currency",
            "original_amount",
            "available_amount",
            "status",
            "created_at",
            "updated_at",
            "applications",
        ]


class FeeConfigurationSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = FeeConfiguration
        fields = [
            "invoice_prefix",
            "receipt_prefix",
            "default_due_days",
            "currency",
            "allow_backdated_payments",
            "auto_apply_advance",
            "updated_at",
        ]

        read_only_fields = [
            "updated_at",
        ]

    def validate(self, attrs):
        instance = self.instance
        requested_currency = attrs.get(
            "currency"
        )

        if (
            instance
            and requested_currency
            and requested_currency
            != instance.currency
            and (
                FeeInvoice.objects.filter(
                    school=instance.school
                ).exists()
                or FeePayment.objects.filter(
                    school=instance.school
                ).exists()
            )
        ):
            raise serializers.ValidationError({
                "currency": [
                    (
                        "Currency cannot be changed "
                        "after the first invoice or "
                        "payment is posted."
                    )
                ]
            })

        return attrs


class StudentFeeWalletSerializer(
    serializers.ModelSerializer
):
    student_detail = UserFeeMiniSerializer(
        source="student",
        read_only=True,
    )

    batch_name = serializers.CharField(
        source="batch.name",
        read_only=True,
    )

    class_name = serializers.CharField(
        source="academic_class.name",
        read_only=True,
    )

    class Meta:
        model = StudentFeeWallet
        fields = [
            "id",
            "student",
            "student_detail",
            "batch",
            "batch_name",
            "academic_class",
            "class_name",
            "total_payable",
            "total_discount",
            "total_scholarship",
            "total_paid",
            "total_due",
            "advance_balance",
            "currency",
            "last_reconciled_at",
            "updated_at",
        ]