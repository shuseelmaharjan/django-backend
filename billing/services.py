from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from billing.models import Invoice, InvoiceLine, InvoiceStatus, Payment, PaymentAllocation, Receipt
from fees.models import StudentCharge, ChargeStatus
from organization.models import SchoolSetting


def _d(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _recalc_invoice_totals(invoice: Invoice):
    subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")
    fine_total = Decimal("0.00")

    for line in invoice.lines.all():
        subtotal += _d(line.amount)
        discount_total += _d(line.discount_amount)

    grand_total = subtotal - discount_total + fine_total

    invoice.subtotal = subtotal
    invoice.discount_total = discount_total
    invoice.fine_total = fine_total
    invoice.grand_total = grand_total
    invoice.save(update_fields=["subtotal", "discount_total", "fine_total", "grand_total"])


def _next_receipt_no(school_id: str) -> str:
    """
    Simple receipt numbering:
    RCPT-000001
    You can replace with per-fiscal-year numbering later.
    """
    settings = SchoolSetting.objects.select_related("school").filter(school_id=school_id).first()
    prefix = settings.receipt_prefix if settings else "RCPT"
    last = Receipt.objects.filter(school_id=school_id, receipt_no__startswith=prefix).order_by("-created_at").first()
    if not last:
        return f"{prefix}-000001"
    try:
        n = int(last.receipt_no.split("-")[-1])
    except Exception:
        n = 0
    return f"{prefix}-{n+1:06d}"


@transaction.atomic
def create_invoice_from_charges(*, school_id: str, student_id, academic_year_id, invoice_no: str, charge_ids: list[str]):
    """
    Conditions:
    - charges must belong to student + year
    - charges must be PENDING (not already invoiced/paid)
    - creates invoice + lines
    - marks charges as INVOICED
    """
    charges = list(StudentCharge.objects.select_related("fee_head").filter(
        id__in=charge_ids,
        student_id=student_id,
        academic_year_id=academic_year_id,
        status=ChargeStatus.PENDING,
    ))

    if not charges:
        raise ValueError("No eligible pending charges found.")

    inv = Invoice.objects.create(
        school_id=school_id,
        student_id=student_id,
        academic_year_id=academic_year_id,
        invoice_no=invoice_no,
        status=InvoiceStatus.DRAFT,
    )

    for ch in charges:
        InvoiceLine.objects.create(
            invoice=inv,
            fee_head=ch.fee_head,
            charge=ch,
            description=ch.fee_head.name,
            amount=ch.base_amount,
            discount_amount=ch.discount_amount,
            final_amount=ch.final_amount,
        )

    _recalc_invoice_totals(inv)

    # mark charges invoiced
    StudentCharge.objects.filter(id__in=[c.id for c in charges]).update(status=ChargeStatus.INVOICED)

    return inv


@transaction.atomic
def allocate_payment(*, payment: Payment, allocations: list[dict]):
    """
    allocations: [{invoice_id, amount}]
    Conditions:
    - invoice belongs to same student
    - cannot allocate more than payment.amount
    - update invoice status to PAID/PARTIALLY_PAID
    """
    remaining = _d(payment.amount)

    for item in allocations:
        invoice_id = item["invoice_id"]
        amt = _d(item["amount"])
        if amt <= 0:
            continue
        if amt > remaining:
            raise ValueError("Allocation exceeds remaining payment amount.")

        inv = Invoice.objects.select_for_update().get(id=invoice_id)
        if inv.student_id != payment.student_id:
            raise ValueError("Invoice does not belong to this student.")
        if inv.status in [InvoiceStatus.VOID]:
            raise ValueError("Cannot allocate to VOID invoice.")

        PaymentAllocation.objects.update_or_create(
            payment=payment,
            invoice=inv,
            defaults={"amount_allocated": amt},
        )

        remaining -= amt

    # Update invoice statuses based on allocated totals
    for alloc in payment.allocations.select_related("invoice").all():
        inv = alloc.invoice
        total_alloc = sum(_d(a.amount_allocated) for a in inv.allocations.all())
        if total_alloc >= _d(inv.grand_total):
            inv.status = InvoiceStatus.PAID
        elif total_alloc > 0:
            inv.status = InvoiceStatus.PARTIALLY_PAID
        else:
            # if draft/issued and no allocations, keep as is
            pass
        inv.save(update_fields=["status"])

    return {"remaining": str(remaining)}
