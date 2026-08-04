from __future__ import annotations

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from fees.models import (
    AdvanceCreditStatus,
    FeeAdvanceCredit,
    FeeInvoice,
    InvoiceStatus,
    StudentFeeWallet,
)
from fees.services.configuration import get_fee_configuration
from fees.services.money import money


@transaction.atomic
def rebuild_wallet(*, enrollment):
    config = get_fee_configuration(enrollment.batch.school)
    wallet, _ = StudentFeeWallet.objects.select_for_update().get_or_create(
        student=enrollment.student,
        batch=enrollment.batch,
        academic_class=enrollment.academic_class,
    )

    invoice_totals = FeeInvoice.objects.filter(
        enrollment=enrollment,
        currency=config.currency,
    ).exclude(status=InvoiceStatus.VOID).aggregate(
        total_payable=Sum("subtotal"),
        total_discount=Sum("discount_amount"),
        total_scholarship=Sum("scholarship_amount"),
        total_paid=Sum("paid_amount"),
        total_due=Sum("due_amount"),
    )
    advance_balance = FeeAdvanceCredit.objects.filter(
        enrollment=enrollment,
        currency=config.currency,
        status__in=[AdvanceCreditStatus.OPEN, AdvanceCreditStatus.CONSUMED],
    ).aggregate(total=Sum("available_amount"))["total"]

    wallet.total_payable = money(invoice_totals["total_payable"])
    wallet.total_discount = money(invoice_totals["total_discount"])
    wallet.total_scholarship = money(invoice_totals["total_scholarship"])
    wallet.total_paid = money(invoice_totals["total_paid"])
    wallet.total_due = money(invoice_totals["total_due"])
    wallet.advance_balance = money(advance_balance)
    wallet.currency = config.currency
    wallet.last_reconciled_at = timezone.now()
    wallet.save(
        update_fields=[
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
    )
    return wallet
