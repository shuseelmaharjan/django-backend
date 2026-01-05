# billing/services.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from billing.models import Invoice, InvoiceLine, Payment, PaymentAllocation, InvoiceStatus, PaymentStatus

def _recalc_invoice_totals(invoice: Invoice) -> None:
    lines = invoice.lines.all()
    subtotal = sum((l.amount for l in lines), Decimal("0.00"))
    discount_total = sum((l.discount_amount for l in lines), Decimal("0.00"))
    fine_total = invoice.fine_total or Decimal("0.00")
    grand_total = subtotal - discount_total + fine_total

    invoice.subtotal = subtotal
    invoice.discount_total = discount_total
    invoice.grand_total = grand_total
    invoice.save(update_fields=["subtotal", "discount_total", "grand_total"])


def _paid_amount(invoice: Invoice) -> Decimal:
    return sum((a.amount_allocated for a in invoice.allocations.select_related("payment").filter(payment__status=PaymentStatus.SUCCESS)), Decimal("0.00"))


def _update_invoice_status(invoice: Invoice) -> None:
    paid = _paid_amount(invoice)
    if invoice.status == InvoiceStatus.VOID:
        return
    if paid <= Decimal("0.00"):
        invoice.status = InvoiceStatus.ISSUED
    elif paid < invoice.grand_total:
        invoice.status = InvoiceStatus.PARTIALLY_PAID
    else:
        invoice.status = InvoiceStatus.PAID
    invoice.save(update_fields=["status"])


@transaction.atomic
def create_invoice_from_charges(*, school_id: str, student, academic_year, invoice_no: str, charges, due_date=None, issue_date=None) -> Invoice:
    issue_date = issue_date or timezone.now().date()
    invoice = Invoice.objects.create(
        school_id=school_id,
        student=student,
        academic_year=academic_year,
        invoice_no=invoice_no,
        issue_date=issue_date,
        due_date=due_date,
        status=InvoiceStatus.ISSUED,
    )

    for ch in charges:
        InvoiceLine.objects.create(
            invoice=invoice,
            fee_head=ch.fee_head,
            charge=ch,
            description=str(ch),
            amount=ch.base_amount,
            discount_amount=ch.discount_amount,
            final_amount=ch.final_amount,
        )

    _recalc_invoice_totals(invoice)
    _update_invoice_status(invoice)
    return invoice


@transaction.atomic
def record_payment_and_allocate(*, school_id: str, student, amount: Decimal, method: str, allocations: list, received_by=None, reference_no="") -> Payment:
    """
    allocations = [{"invoice": invoice_obj, "amount": Decimal("500.00")}, ...]
    """
    payment = Payment.objects.create(
        school_id=school_id,
        student=student,
        amount=amount,
        method=method,
        received_by=received_by,
        reference_no=reference_no,
        status=PaymentStatus.SUCCESS,
    )

    for item in allocations:
        PaymentAllocation.objects.create(
            payment=payment,
            invoice=item["invoice"],
            amount_allocated=item["amount"],
        )
        _update_invoice_status(item["invoice"])

    return payment
