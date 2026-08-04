from __future__ import annotations

from datetime import timedelta
import hashlib
import json

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academics.models import EnrollmentStatus, StudentEnrollments
from fees.models import (
    AdvanceApplicationStatus,
    AdvanceCreditStatus,
    AllocationStatus,
    DocumentSequenceKind,
    FeeAdvanceApplication,
    FeeAdvanceCredit,
    FeeInvoice,
    FeePayment,
    FeePaymentAllocation,
    FeePaymentReversal,
    InvoiceStatus,
    PaymentStatus,
)
from fees.services.audit import audit
from fees.services.configuration import get_fee_configuration
from fees.services.money import MONEY_ZERO, money
from fees.services.numbering import next_document_number
from fees.services.wallet_service import rebuild_wallet


def _payment_fingerprint(*, enrollment_id, amount, payment_method, invoice_ids, auto_allocate, external_reference, notes):
    payload = {
        "enrollment_id": str(enrollment_id),
        "amount": str(money(amount)),
        "payment_method": payment_method,
        "invoice_ids": [str(value) for value in (invoice_ids or [])],
        "auto_allocate": bool(auto_allocate),
        "external_reference": (external_reference or "").strip(),
        "notes": (notes or "").strip(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _invoice_status(total_amount, paid_amount):
    if paid_amount >= total_amount:
        return InvoiceStatus.PAID
    if paid_amount > 0:
        return InvoiceStatus.PARTIALLY_PAID
    return InvoiceStatus.ISSUED



def _account_totals(enrollment, currency):
    foreign_exists = FeeInvoice.objects.filter(enrollment=enrollment).exclude(status=InvoiceStatus.VOID).exclude(currency=currency).exists()
    if foreign_exists:
        raise ValidationError({"currency": ["This enrollment contains invoices in more than one currency; payment is blocked until reconciled."]})
    totals = FeeInvoice.objects.filter(enrollment=enrollment, currency=currency).exclude(status=InvoiceStatus.VOID).aggregate(
        gross=Sum("subtotal"),
        discount=Sum("discount_amount"),
        scholarship=Sum("scholarship_amount"),
        net=Sum("total_amount"),
        paid=Sum("paid_amount"),
        due=Sum("due_amount"),
    )
    return {key: money(value) for key, value in totals.items()}


def _advance_balance(enrollment, currency):
    return money(
        FeeAdvanceCredit.objects.filter(
            enrollment=enrollment,
            currency=currency,
            status__in=[AdvanceCreditStatus.OPEN, AdvanceCreditStatus.CONSUMED],
        ).aggregate(total=Sum("available_amount"))["total"]
    )


def _locked_enrollment(*, school, enrollment):
    locked = (
        StudentEnrollments.objects.select_for_update()
        .select_related("student", "batch__school", "academic_class")
        .get(pk=enrollment.pk)
    )
    if locked.batch.school_id != school.id:
        raise ValidationError({"enrollment_id": ["Enrollment does not belong to your school."]})
    if locked.status != EnrollmentStatus.ENROLLED:
        raise ValidationError({"enrollment_id": ["Payments can only be posted to an active enrollment."]})
    return locked


@transaction.atomic
def post_payment(
    *,
    school,
    enrollment,
    actor,
    amount,
    paid_at,
    payment_method,
    idempotency_key,
    invoice_ids: list | None = None,
    auto_allocate: bool = True,
    external_reference: str = "",
    notes: str = "",
):
    enrollment = _locked_enrollment(school=school, enrollment=enrollment)
    amount = money(amount)
    if amount <= 0:
        raise ValidationError({"amount": ["Payment amount must be greater than zero."]})

    config = get_fee_configuration(school)
    fingerprint = _payment_fingerprint(
        enrollment_id=enrollment.id,
        amount=amount,
        payment_method=payment_method,
        invoice_ids=invoice_ids,
        auto_allocate=auto_allocate,
        external_reference=external_reference,
        notes=notes,
    )
    existing = FeePayment.objects.filter(school=school, idempotency_key=idempotency_key).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError({"idempotency_key": ["This key was already used for a different payment request."]})
        return existing, False

    now = timezone.now()
    if paid_at > now + timedelta(minutes=5):
        raise ValidationError({"paid_at": ["Payment time cannot be in the future."]})
    if not config.allow_backdated_payments and timezone.localtime(paid_at).date() != timezone.localdate():
        raise ValidationError({"paid_at": ["Backdated payments are disabled for this school."]})
    if timezone.localtime(paid_at).date() < timezone.localtime(enrollment.enrolled_at).date():
        raise ValidationError({"paid_at": ["Payment date cannot be before the enrollment date."]})

    before_totals = _account_totals(enrollment, config.currency)
    before_due = before_totals["due"]
    receipt_number = next_document_number(
        school=school,
        kind=DocumentSequenceKind.RECEIPT,
        document_date=timezone.localtime(paid_at).date(),
    )
    try:
        with transaction.atomic():
            payment = FeePayment.objects.create(
                school=school,
                enrollment=enrollment,
                student=enrollment.student,
                batch=enrollment.batch,
                academic_class=enrollment.academic_class,
                receipt_number=receipt_number,
                paid_at=paid_at,
                amount=amount,
                currency=config.currency,
                payment_method=payment_method,
                external_reference=(external_reference or "").strip(),
                notes=(notes or "").strip(),
                status=PaymentStatus.POSTED,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                account_gross_amount=before_totals["gross"],
                account_discount_amount=before_totals["discount"],
                account_scholarship_amount=before_totals["scholarship"],
                account_net_amount=before_totals["net"],
                before_payment_due=before_due,
                received_by=actor,
            )
    except IntegrityError:
        existing = FeePayment.objects.filter(school=school, idempotency_key=idempotency_key).first()
        if existing and existing.request_fingerprint == fingerprint:
            return existing, False
        raise ValidationError({"idempotency_key": ["This key was already used for another payment."]})

    selected: list[FeeInvoice] = []
    seen_ids = set()
    if invoice_ids:
        locked = list(
            FeeInvoice.objects.select_for_update()
            .filter(id__in=invoice_ids)
            .select_related("student", "enrollment")
        )
        locked_map = {str(invoice.id): invoice for invoice in locked}
        missing = [str(value) for value in invoice_ids if str(value) not in locked_map]
        if missing:
            raise ValidationError({"invoice_ids": ["Invoices not found: " + ", ".join(missing)]})
        for invoice_id in invoice_ids:
            invoice = locked_map[str(invoice_id)]
            if invoice.id in seen_ids:
                continue
            if invoice.enrollment_id != enrollment.id or invoice.school_id != school.id:
                raise ValidationError({"invoice_ids": [f"Invoice {invoice.id} belongs to another student or school."]})
            if invoice.status == InvoiceStatus.VOID:
                raise ValidationError({"invoice_ids": [f"Invoice {invoice.invoice_number} is void."]})
            if invoice.currency != config.currency:
                raise ValidationError({"invoice_ids": [f"Invoice {invoice.invoice_number} uses {invoice.currency}, not {config.currency}."]})
            if invoice.due_amount <= 0:
                continue
            selected.append(invoice)
            seen_ids.add(invoice.id)

    if auto_allocate:
        oldest = list(
            FeeInvoice.objects.select_for_update()
            .filter(enrollment=enrollment, currency=config.currency, due_amount__gt=0)
            .exclude(status=InvoiceStatus.VOID)
            .exclude(id__in=seen_ids)
            .order_by("due_date", "invoice_date", "created_at", "id")
        )
        selected.extend(oldest)

    remaining = amount
    allocated_total = MONEY_ZERO
    for invoice in selected:
        if remaining <= 0:
            break
        allocation_amount = min(money(invoice.due_amount), remaining)
        if allocation_amount <= 0:
            continue
        FeePaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice,
            amount=allocation_amount,
            status=AllocationStatus.ACTIVE,
        )
        invoice.paid_amount = money(invoice.paid_amount + allocation_amount)
        invoice.due_amount = money(invoice.total_amount - invoice.paid_amount)
        invoice.status = _invoice_status(invoice.total_amount, invoice.paid_amount)
        invoice.save(update_fields=["paid_amount", "due_amount", "status", "updated_at"])
        allocated_total = money(allocated_total + allocation_amount)
        remaining = money(remaining - allocation_amount)

    if remaining > 0:
        FeeAdvanceCredit.objects.create(
            school=school,
            enrollment=enrollment,
            student=enrollment.student,
            payment=payment,
            original_amount=remaining,
            currency=config.currency,
            available_amount=remaining,
            status=AdvanceCreditStatus.OPEN,
        )

    after_totals = _account_totals(enrollment, config.currency)
    after_due = after_totals["due"]
    advance_balance_after = _advance_balance(enrollment, config.currency)
    payment.account_paid_after = after_totals["paid"]
    payment.after_payment_due = after_due
    payment.advance_created = remaining
    payment.advance_balance_after = advance_balance_after
    payment.save(
        update_fields=["account_paid_after", "after_payment_due", "advance_created", "advance_balance_after"]
    )
    rebuild_wallet(enrollment=enrollment)
    audit(
        school=school,
        actor=actor,
        event_type="PAYMENT_POSTED",
        entity=payment,
        payload={
            "receipt_number": payment.receipt_number,
            "amount": str(payment.amount),
            "allocated": str(allocated_total),
            "advance_created": str(remaining),
            "before_due": str(before_due),
            "after_due": str(after_due),
            "payment_method": payment.payment_method,
        },
    )
    return payment, True


@transaction.atomic
def reverse_payment(*, school, payment, actor, reason: str):
    payment = (
        FeePayment.objects.select_for_update()
        .select_related("enrollment", "student", "school")
        .get(pk=payment.pk)
    )
    if payment.school_id != school.id:
        raise ValidationError({"payment": ["Payment does not belong to your school."]})
    if payment.status == PaymentStatus.REVERSED:
        return payment, False
    if not reason or not reason.strip():
        raise ValidationError({"reason": ["A reversal reason is required."]})

    credit = FeeAdvanceCredit.objects.select_for_update().filter(payment=payment).first()
    if credit:
        active_applications = FeeAdvanceApplication.objects.select_for_update().filter(
            credit=credit,
            status=AdvanceApplicationStatus.ACTIVE,
        )
        if active_applications.exists():
            invoice_numbers = list(active_applications.values_list("invoice__invoice_number", flat=True))
            raise ValidationError({
                "payment": [
                    "This payment's advance has already been used on invoices: "
                    + ", ".join(invoice_numbers)
                    + ". Reverse or settle those dependent invoices first."
                ]
            })
        credit.available_amount = MONEY_ZERO
        credit.status = AdvanceCreditStatus.REVERSED
        credit.save(update_fields=["available_amount", "status", "updated_at"])

    allocations = list(
        FeePaymentAllocation.objects.select_for_update()
        .select_related("invoice")
        .filter(payment=payment, status=AllocationStatus.ACTIVE)
        .order_by("created_at", "id")
    )
    reversal_time = timezone.now()
    for allocation in allocations:
        invoice = FeeInvoice.objects.select_for_update().get(pk=allocation.invoice_id)
        invoice.paid_amount = money(invoice.paid_amount - allocation.amount)
        if invoice.paid_amount < 0:
            raise ValidationError({"payment": ["Allocation reversal would make an invoice paid amount negative."]})
        invoice.due_amount = money(invoice.total_amount - invoice.paid_amount)
        invoice.status = _invoice_status(invoice.total_amount, invoice.paid_amount)
        invoice.save(update_fields=["paid_amount", "due_amount", "status", "updated_at"])
        allocation.status = AllocationStatus.REVERSED
        allocation.reversed_at = reversal_time
        allocation.reversed_by = actor
        allocation.save(update_fields=["status", "reversed_at", "reversed_by"])

    FeePaymentReversal.objects.create(
        payment=payment,
        amount=payment.amount,
        reason=reason.strip(),
        reversed_by=actor,
    )
    payment.status = PaymentStatus.REVERSED
    payment.save(update_fields=["status"])
    rebuild_wallet(enrollment=payment.enrollment)
    audit(
        school=school,
        actor=actor,
        event_type="PAYMENT_REVERSED",
        entity=payment,
        payload={
            "receipt_number": payment.receipt_number,
            "amount": str(payment.amount),
            "reason": reason.strip(),
        },
    )
    return payment, True
