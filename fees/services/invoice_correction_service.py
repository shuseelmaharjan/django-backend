from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from fees.models import (
    AdvanceApplicationStatus,
    AdvanceCreditStatus,
    AllocationStatus,
    FeeAdvanceApplication,
    FeeAdvanceCredit,
    FeeInvoice,
    FeePaymentAllocation,
    InvoiceStatus,
)
from fees.services.audit import audit
from fees.services.money import money
from fees.services.wallet_service import rebuild_wallet


@transaction.atomic
def void_invoice(*, school, invoice, actor, reason: str):
    invoice = FeeInvoice.objects.select_for_update().select_related("enrollment").get(pk=invoice.pk)
    if invoice.school_id != school.id:
        raise ValidationError({"invoice": ["Invoice does not belong to your school."]})
    if invoice.status == InvoiceStatus.VOID:
        return invoice, False
    if not reason or not reason.strip():
        raise ValidationError({"reason": ["A void reason is required."]})

    active_allocations = FeePaymentAllocation.objects.select_for_update().filter(
        invoice=invoice,
        status=AllocationStatus.ACTIVE,
    )
    if active_allocations.exists():
        receipts = list(active_allocations.values_list("payment__receipt_number", flat=True))
        raise ValidationError({
            "invoice": [
                "Reverse the payments allocated to this invoice first: " + ", ".join(receipts)
            ]
        })

    applications = list(
        FeeAdvanceApplication.objects.select_for_update()
        .select_related("credit")
        .filter(invoice=invoice, status=AdvanceApplicationStatus.ACTIVE)
    )
    reversal_time = timezone.now()
    for application in applications:
        credit = FeeAdvanceCredit.objects.select_for_update().get(pk=application.credit_id)
        credit.available_amount = money(credit.available_amount + application.amount)
        credit.status = AdvanceCreditStatus.OPEN
        credit.save(update_fields=["available_amount", "status", "updated_at"])
        application.status = AdvanceApplicationStatus.REVERSED
        application.reversed_at = reversal_time
        application.reversed_by = actor
        application.save(update_fields=["status", "reversed_at", "reversed_by"])

    # Release the canonical billing key so a corrected replacement invoice can be
    # issued for the same enrollment and period without deleting audit evidence.
    invoice.billing_key = f"{invoice.billing_key}:VOID:{invoice.id}"
    invoice.status = InvoiceStatus.VOID
    invoice.voided_by = actor
    invoice.voided_at = reversal_time
    invoice.void_reason = reason.strip()
    invoice.save(
        update_fields=[
            "billing_key", "status", "voided_by", "voided_at", "void_reason", "updated_at"
        ]
    )
    rebuild_wallet(enrollment=invoice.enrollment)
    audit(
        school=school,
        actor=actor,
        event_type="INVOICE_VOIDED",
        entity=invoice,
        payload={"invoice_number": invoice.invoice_number, "reason": reason.strip()},
    )
    return invoice, True
