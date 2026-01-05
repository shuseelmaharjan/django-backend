# billing/models.py
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone

class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    PARTIALLY_PAID = "partially_paid", "Partially Paid"
    PAID = "paid", "Paid"
    VOID = "void", "Void"


class PaymentStatus(models.TextChoices):
    INITIATED = "initiated", "Initiated"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    BANK = "bank", "Bank"
    ONLINE = "online", "Online"
    WALLET = "wallet", "Wallet"


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="invoices")
    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.CASCADE, related_name="invoices")

    invoice_no = models.CharField(max_length=40, db_index=True)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    fine_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT, db_index=True)
    notes = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="+")
    voided_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="+")
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school_id", "invoice_no"], name="uq_school_invoice_no"),
        ]
        indexes = [
            models.Index(fields=["student", "academic_year", "status"]),
            models.Index(fields=["school_id", "status", "issue_date"]),
        ]

    def __str__(self):
        return f"{self.invoice_no} - {self.student.user.email}"


class InvoiceLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")

    fee_head = models.ForeignKey("fees.FeeHead", on_delete=models.PROTECT)
    charge = models.ForeignKey("fees.StudentCharge", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    description = models.CharField(max_length=200, blank=True, default="")

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        indexes = [
            models.Index(fields=["invoice", "fee_head"]),
        ]


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="payments")

    payment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH, db_index=True)
    reference_no = models.CharField(max_length=80, blank=True, default="")

    received_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.INITIATED, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    refunded_at = models.DateTimeField(null=True, blank=True)
    refunded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+")
    class Meta:
        indexes = [
            models.Index(fields=["school_id", "status", "payment_date"]),
            models.Index(fields=["student", "payment_date"]),
        ]

    def __str__(self):
        return f"Payment({self.student.user.email} - {self.amount})"


class PaymentAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="allocations")
    amount_allocated = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payment", "invoice"], name="uq_payment_invoice_allocation"),
        ]
        indexes = [
            models.Index(fields=["invoice"]),
        ]


class OnlinePaymentSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="online_payment_sessions")
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_sessions")

    gateway = models.CharField(max_length=30, db_index=True)  # "khalti", "esewa", "imepay"
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    session_id = models.CharField(max_length=120, db_index=True, blank=True, default="")
    gateway_payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.INITIATED, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Receipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name="receipt")
    receipt_no = models.CharField(max_length=40, db_index=True)

    generated_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school_id", "receipt_no"], name="uq_school_receipt_no"),
        ]
