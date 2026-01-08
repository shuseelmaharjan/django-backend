from rest_framework import serializers
from billing.models import Invoice, InvoiceLine, Payment, PaymentAllocation, Receipt


class InvoiceLineSerializer(serializers.ModelSerializer):
    fee_head_code = serializers.CharField(source="fee_head.code", read_only=True)

    class Meta:
        model = InvoiceLine
        fields = [
            "id", "invoice",
            "fee_head", "fee_head_code",
            "charge",
            "description",
            "amount", "discount_amount", "final_amount",
        ]
        read_only_fields = ["id"]


class InvoiceSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "school_id",
            "student", "student_email",
            "academic_year",
            "invoice_no", "issue_date", "due_date",
            "subtotal", "discount_total", "fine_total", "grand_total",
            "status", "notes",
            "created_at", "created_by",
            "voided_at", "void_reason",
            "lines",
        ]
        read_only_fields = [
            "id", "school_id",
            "subtotal", "discount_total", "fine_total", "grand_total",
            "created_at", "created_by", "voided_at",
        ]


class InvoiceCreateFromChargesSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    academic_year_id = serializers.UUIDField()
    invoice_no = serializers.CharField()
    charge_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)


class PaymentSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source="student.user.email", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "school_id",
            "student", "student_email",
            "payment_date", "amount",
            "method", "reference_no",
            "received_by", "status",
            "created_at",
        ]
        read_only_fields = ["id", "school_id", "created_at"]


class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_no = serializers.CharField(source="invoice.invoice_no", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ["id", "payment", "invoice", "invoice_no", "amount_allocated"]
        read_only_fields = ["id"]


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = ["id", "school_id", "payment", "receipt_no", "generated_file", "created_at"]
        read_only_fields = ["id", "school_id", "receipt_no", "created_at"]
