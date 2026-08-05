from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academics.models import EnrollmentStatus, StudentEnrollments
from fees.models import (
    AdvanceApplicationStatus,
    AdvanceCreditStatus,
    ConcessionCalculation,
    ConcessionFrequency,
    ConcessionKind,
    ConcessionStatus,
    DocumentSequenceKind,
    FeeAdvanceApplication,
    FeeAdvanceCredit,
    FeeInclude,
    FeeInvoice,
    FeeInvoiceAdjustment,
    FeeInvoiceLine,
    FeePeriod,
    FeeScope,
    FeeStatus,
    FeeStructure,
    InvoiceStatus,
    StudentFeeConcession,
)
from fees.services.audit import audit
from fees.services.configuration import get_fee_configuration
from fees.services.dates import count_recurrences
from fees.services.money import MONEY_ZERO, money
from fees.services.numbering import next_document_number
from fees.services.wallet_service import rebuild_wallet


@dataclass
class LineDraft:
    structure: FeeStructure
    quantity: Decimal
    gross: Decimal
    discount: Decimal = MONEY_ZERO
    scholarship: Decimal = MONEY_ZERO
    adjustments: list[tuple[StudentFeeConcession, Decimal]] = field(default_factory=list)

    @property
    def remaining(self) -> Decimal:
        return money(self.gross - self.discount - self.scholarship)

    @property
    def net(self) -> Decimal:
        return self.remaining


def _validate_enrollment(*, enrollment, school):
    if enrollment.batch.school_id != school.id:
        raise ValidationError({"enrollment_id": ["Enrollment does not belong to your school."]})
    if enrollment.student_id is None:
        raise ValidationError({"enrollment_id": ["Enrollment has no student."]})
    if enrollment.status != EnrollmentStatus.ENROLLED:
        raise ValidationError({"enrollment_id": ["Only currently enrolled students can be billed."]})


def _applicable_structures(enrollment) -> list[FeeStructure]:
    explicit_structure_ids = list(
        FeeInclude.objects
        .filter(
            user_id=enrollment.student_id,
            batch_id=enrollment.batch_id,
            classroom_id=enrollment.academic_class_id,
            status=FeeStatus.active,
            fees__school_id=enrollment.batch.school_id,
            fees__status=FeeStatus.active,
        )
        .values_list("fees_id", flat=True)
    )

    if explicit_structure_ids:
        return list(
            FeeStructure.objects
            .select_related(
                "fee_head",
                "school",
                "batch",
                "academic_class",
            )
            .filter(
                id__in=explicit_structure_ids,
                status=FeeStatus.active,
            )
            .order_by("fee_head__name", "period", "id")
        )

    return list(
        FeeStructure.objects
        .select_related(
            "fee_head",
            "school",
            "batch",
            "academic_class",
        )
        .filter(
            school_id=enrollment.batch.school_id,
            status=FeeStatus.active,
        )
        .filter(
            Q(scope=FeeScope.GLOBAL)
            | Q(
                scope=FeeScope.BATCH,
                batch_id=enrollment.batch_id,
            )
            | Q(
                scope=FeeScope.CLASS,
                academic_class_id=enrollment.academic_class_id,
            )
            | Q(
                scope=FeeScope.BATCH_CLASS,
                batch_id=enrollment.batch_id,
                academic_class_id=enrollment.academic_class_id,
            )
        )
        .order_by("fee_head__name", "period", "id")
    )

def _structure_quantity(*, structure, enrollment, period_start: date, period_end: date) -> Decimal:
    prior_exists = FeeInvoiceLine.objects.filter(
        invoice__enrollment=enrollment,
        invoice__status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID],
        fee_structure=structure,
    ).exists()

    if structure.period == FeePeriod.ONE_TIME:
        return Decimal("0.00") if prior_exists else Decimal("1.00")
    if structure.period == FeePeriod.OTHER:
        # OTHER is safe for automatic billing only when explicitly assigned, and only once.
        explicitly_assigned = FeeInclude.objects.filter(
            fees=structure,
            user=enrollment.student,
            batch=enrollment.batch,
            classroom=enrollment.academic_class,
            status=FeeStatus.active,
        ).exists()
        return Decimal("1.00") if explicitly_assigned and not prior_exists else Decimal("0.00")

    interval = {
        FeePeriod.MONTHLY: 1,
        FeePeriod.QUARTERLY: 3,
        FeePeriod.SEMESTER: 6,
        FeePeriod.ANNUAL: 12,
    }.get(structure.period)
    if not interval:
        return Decimal("0.00")

    anchor = enrollment.batch.start_date_ad
    count = count_recurrences(anchor, period_start, period_end, interval)
    return Decimal(count).quantize(Decimal("0.00"))


def _build_line_drafts(*, structures, enrollment, period_start, period_end) -> list[LineDraft]:
    drafts: list[LineDraft] = []
    for structure in structures:
        quantity = _structure_quantity(
            structure=structure,
            enrollment=enrollment,
            period_start=period_start,
            period_end=period_end,
        )
        if quantity <= 0:
            continue
        gross = money(structure.amount * quantity)
        drafts.append(LineDraft(structure=structure, quantity=quantity, gross=gross))
    return drafts


def _historical_concession_used(concession) -> Decimal:
    total = FeeInvoiceAdjustment.objects.filter(
        concession=concession,
        invoice_line__invoice__status__in=[
            InvoiceStatus.ISSUED,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PAID,
        ],
    ).aggregate(total=Sum("amount"))["total"]
    return money(total)


def _merge_adjustment(*, draft: LineDraft, concession, amount: Decimal) -> None:
    """Keep one immutable adjustment row per concession and invoice line."""
    for index, (existing, existing_amount) in enumerate(draft.adjustments):
        if existing.pk == concession.pk:
            draft.adjustments[index] = (existing, money(existing_amount + amount))
            return
    draft.adjustments.append((concession, money(amount)))


def _distribute_amount(*, drafts: list[LineDraft], total: Decimal, kind: str, concession) -> Decimal:
    total = money(total)
    available = [draft.remaining for draft in drafts]
    available_total = money(sum(available, MONEY_ZERO))
    if total <= 0 or available_total <= 0:
        return MONEY_ZERO
    total = min(total, available_total)

    assigned = MONEY_ZERO
    for index, draft in enumerate(drafts):
        if draft.remaining <= 0:
            continue
        if index == len(drafts) - 1:
            portion = money(total - assigned)
        else:
            portion = money(total * draft.remaining / available_total)
            portion = min(portion, draft.remaining)
        if portion <= 0:
            continue
        if kind == ConcessionKind.DISCOUNT:
            draft.discount = money(draft.discount + portion)
        else:
            draft.scholarship = money(draft.scholarship + portion)
        _merge_adjustment(draft=draft, concession=concession, amount=portion)
        assigned = money(assigned + portion)
        if assigned >= total:
            break

    # Rounding can leave one paisa. Put it on the first line that can accept it.
    remainder = money(total - assigned)
    if remainder > 0:
        for draft in drafts:
            if draft.remaining >= remainder:
                if kind == ConcessionKind.DISCOUNT:
                    draft.discount = money(draft.discount + remainder)
                else:
                    draft.scholarship = money(draft.scholarship + remainder)
                _merge_adjustment(draft=draft, concession=concession, amount=remainder)
                assigned = money(assigned + remainder)
                break
    return assigned


def _apply_concessions(*, drafts, enrollment, period_start, period_end):
    concessions = list(
        StudentFeeConcession.objects.select_for_update()
        .filter(
            school=enrollment.batch.school,
            student=enrollment.student,
            batch=enrollment.batch,
            academic_class=enrollment.academic_class,
            status=ConcessionStatus.ACTIVE,
            valid_from__lte=period_end,
        )
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=period_start))
        .order_by("kind", "created_at", "id")
    )

    for concession in concessions:
        used = _historical_concession_used(concession)
        if concession.frequency == ConcessionFrequency.ONE_TIME and used > 0:
            continue

        eligible = [
            draft
            for draft in drafts
            if draft.remaining > 0
            and (concession.fee_head_id is None or draft.structure.fee_head_id == concession.fee_head_id)
        ]
        if not eligible:
            continue

        eligible_total = money(sum((draft.remaining for draft in eligible), MONEY_ZERO))
        if concession.calculation == ConcessionCalculation.PERCENTAGE:
            requested = money(eligible_total * concession.value / Decimal("100.00"))
        else:
            requested = money(concession.value)

        if concession.maximum_total_amount is not None:
            remaining_cap = money(concession.maximum_total_amount - used)
            requested = min(requested, max(remaining_cap, MONEY_ZERO))
        if concession.frequency == ConcessionFrequency.ONE_TIME:
            requested = min(requested, money(concession.value) if concession.calculation == ConcessionCalculation.FIXED else requested)

        _distribute_amount(
            drafts=eligible,
            total=requested,
            kind=concession.kind,
            concession=concession,
        )


def _invoice_status(total_amount: Decimal, paid_amount: Decimal) -> str:
    if paid_amount >= total_amount:
        return InvoiceStatus.PAID
    if paid_amount > 0:
        return InvoiceStatus.PARTIALLY_PAID
    return InvoiceStatus.ISSUED


def _apply_advance_to_invoice(*, invoice, actor) -> Decimal:
    remaining_due = money(invoice.due_amount)
    if remaining_due <= 0:
        return MONEY_ZERO

    credits = list(
        FeeAdvanceCredit.objects.select_for_update()
        .filter(
            enrollment=invoice.enrollment,
            currency=invoice.currency,
            status__in=[AdvanceCreditStatus.OPEN, AdvanceCreditStatus.CONSUMED],
            available_amount__gt=0,
        )
        .order_by("created_at", "id")
    )
    applied_total = MONEY_ZERO
    for credit in credits:
        if remaining_due <= 0:
            break
        amount = min(money(credit.available_amount), remaining_due)
        if amount <= 0:
            continue
        FeeAdvanceApplication.objects.create(
            credit=credit,
            invoice=invoice,
            amount=amount,
            applied_by=actor,
            status=AdvanceApplicationStatus.ACTIVE,
        )
        credit.available_amount = money(credit.available_amount - amount)
        credit.status = AdvanceCreditStatus.CONSUMED if credit.available_amount == 0 else AdvanceCreditStatus.OPEN
        credit.save(update_fields=["available_amount", "status", "updated_at"])
        applied_total = money(applied_total + amount)
        remaining_due = money(remaining_due - amount)

    if applied_total > 0:
        invoice.advance_applied = money(invoice.advance_applied + applied_total)
        invoice.paid_amount = money(invoice.paid_amount + applied_total)
        invoice.due_amount = money(invoice.total_amount - invoice.paid_amount)
        invoice.status = _invoice_status(invoice.total_amount, invoice.paid_amount)
        invoice.save(update_fields=["advance_applied", "paid_amount", "due_amount", "status", "updated_at"])
    return applied_total


@transaction.atomic
def generate_invoice(
    *,
    school,
    enrollment,
    period_start: date,
    period_end: date,
    actor,
    invoice_date: date | None = None,
    due_date: date | None = None,
    apply_advance: bool | None = None,
    notes: str = "",
    idempotency_key: str | None = None,
):
    enrollment = (
        StudentEnrollments.objects.select_for_update()
        .select_related("student", "batch__school", "academic_class")
        .get(pk=enrollment.pk)
    )
    _validate_enrollment(enrollment=enrollment, school=school)

    if period_end < period_start:
        raise ValidationError({"period_end": ["period_end must be on or after period_start."]})
    if period_start < enrollment.batch.start_date_ad or period_end > enrollment.batch.end_date_ad:
        raise ValidationError({
            "date_range": [
                f"Billing range must be inside batch dates {enrollment.batch.start_date_ad} to {enrollment.batch.end_date_ad}."
            ]
        })
    enrollment_date = timezone.localtime(enrollment.enrolled_at).date()
    if period_end < enrollment_date:
        raise ValidationError({"date_range": ["Billing range ends before the student was enrolled."]})

    invoice_date = invoice_date or timezone.localdate()
    config = get_fee_configuration(school)
    due_date = due_date or (invoice_date + timedelta(days=config.default_due_days))
    if due_date < invoice_date:
        raise ValidationError({"due_date": ["due_date cannot be before invoice_date."]})
    if idempotency_key:
        existing_by_key = FeeInvoice.objects.filter(school=school, idempotency_key=idempotency_key).first()
        if existing_by_key:
            if (
                existing_by_key.enrollment_id != enrollment.id
                or existing_by_key.period_start != period_start
                or existing_by_key.period_end != period_end
            ):
                raise ValidationError({"idempotency_key": ["This key was already used for a different invoice request."]})
            return existing_by_key, False

    billing_key = FeeInvoice.make_billing_key(enrollment.id, period_start, period_end)
    existing = FeeInvoice.objects.select_for_update().filter(billing_key=billing_key).first()
    if existing:
        return existing, False

    structures = _applicable_structures(enrollment)
    drafts = _build_line_drafts(
        structures=structures,
        enrollment=enrollment,
        period_start=period_start,
        period_end=period_end,
    )
    if not drafts:
        raise ValidationError({"fees": ["No fee items are due for this student in the requested date range."]})

    structure_currencies = {draft.structure.currency for draft in drafts}
    if len(structure_currencies) != 1:
        raise ValidationError({"currency": ["A single invoice cannot combine fee structures in different currencies."]})
    invoice_currency = next(iter(structure_currencies))
    if invoice_currency != config.currency:
        raise ValidationError({
            "currency": [
                f"Fee structure currency {invoice_currency} does not match the school's configured fee currency {config.currency}."
            ]
        })

    _apply_concessions(
        drafts=drafts,
        enrollment=enrollment,
        period_start=period_start,
        period_end=period_end,
    )

    subtotal = money(sum((draft.gross for draft in drafts), MONEY_ZERO))
    discount = money(sum((draft.discount for draft in drafts), MONEY_ZERO))
    scholarship = money(sum((draft.scholarship for draft in drafts), MONEY_ZERO))
    total = money(subtotal - discount - scholarship)
    opening_due = money(
        FeeInvoice.objects
        .filter(enrollment=enrollment, currency=invoice_currency)
        .exclude(status=InvoiceStatus.VOID)
        .aggregate(total=Sum("due_amount"))["total"]
    )

    invoice_number = next_document_number(
        school=school,
        kind=DocumentSequenceKind.INVOICE,
        document_date=invoice_date,
    )
    try:
        with transaction.atomic():
            invoice = FeeInvoice.objects.create(
                school=school,
                enrollment=enrollment,
                student=enrollment.student,
                batch=enrollment.batch,
                academic_class=enrollment.academic_class,
                invoice_number=invoice_number,
                billing_key=billing_key,
                period_start=period_start,
                period_end=period_end,
                invoice_date=invoice_date,
                due_date=due_date,
                status=InvoiceStatus.PAID if total == 0 else InvoiceStatus.ISSUED,
                currency=invoice_currency,
                subtotal=subtotal,
                discount_amount=discount,
                scholarship_amount=scholarship,
                total_amount=total,
                paid_amount=MONEY_ZERO,
                advance_applied=MONEY_ZERO,
                due_amount=total,
                opening_due_amount=opening_due,
                account_due_at_issue=money(opening_due + total),
                notes=(notes or "").strip(),
                idempotency_key=idempotency_key or None,
                generated_by=actor,
            )
    except IntegrityError:
        existing = FeeInvoice.objects.filter(billing_key=billing_key).first()
        if existing:
            return existing, False
        if idempotency_key:
            existing = FeeInvoice.objects.filter(school=school, idempotency_key=idempotency_key).first()
            if existing:
                if (
                    existing.enrollment_id == enrollment.id
                    and existing.period_start == period_start
                    and existing.period_end == period_end
                ):
                    return existing, False
                raise ValidationError({"idempotency_key": ["This key was already used for another invoice."]})
        raise

    line_map: dict[int, FeeInvoiceLine] = {}
    for draft in drafts:
        structure = draft.structure
        line = FeeInvoiceLine.objects.create(
            invoice=invoice,
            fee_structure=structure,
            fee_head=structure.fee_head,
            fee_head_code=structure.fee_head.code,
            fee_head_name=structure.fee_head.name,
            fee_period=structure.period,
            description=structure.fee_head.description or "",
            quantity=draft.quantity,
            unit_amount=money(structure.amount),
            gross_amount=draft.gross,
            discount_amount=draft.discount,
            scholarship_amount=draft.scholarship,
            net_amount=draft.net,
            source_start=period_start,
            source_end=period_end,
        )
        line_map[id(draft)] = line
        for concession, amount in draft.adjustments:
            FeeInvoiceAdjustment.objects.create(
                invoice_line=line,
                concession=concession,
                kind=concession.kind,
                amount=amount,
                reason=concession.reason,
            )

    should_apply_advance = config.auto_apply_advance if apply_advance is None else apply_advance
    if should_apply_advance and invoice.due_amount > 0:
        _apply_advance_to_invoice(invoice=invoice, actor=actor)
        invoice.refresh_from_db()

    invoice.account_due_at_issue = money(opening_due + invoice.due_amount)
    invoice.save(update_fields=["account_due_at_issue", "updated_at"])
    rebuild_wallet(enrollment=enrollment)
    audit(
        school=school,
        actor=actor,
        event_type="INVOICE_ISSUED",
        entity=invoice,
        payload={
            "invoice_number": invoice.invoice_number,
            "period_start": str(period_start),
            "period_end": str(period_end),
            "subtotal": str(invoice.subtotal),
            "discount": str(invoice.discount_amount),
            "scholarship": str(invoice.scholarship_amount),
            "advance_applied": str(invoice.advance_applied),
            "due": str(invoice.due_amount),
        },
    )
    return invoice, True


@transaction.atomic
def bulk_generate_invoices(
    *,
    school,
    actor,
    period_start: date,
    period_end: date,
    student_ids: list | None = None,
    enrollment_ids: list | None = None,
    batch_id=None,
    academic_class_id=None,
    section_id=None,
    invoice_date: date | None = None,
    due_date: date | None = None,
    apply_advance: bool | None = None,
    notes: str = "",
):
    """
    Generate invoices for multiple active enrollments.

    Selection must be based on exactly one of:
    - enrollment_ids
    - student_ids
    - batch_id, optionally filtered by class and section

    Existing invoices are returned instead of duplicated.

    Important:
    The enrollment rows are locked first without nullable joins.
    Related objects are then loaded in a second query inside the same
    transaction. This avoids PostgreSQL's:

        FOR UPDATE cannot be applied to the nullable side
        of an outer join
    """

    lock_queryset = (
        StudentEnrollments.objects
        .select_for_update()
        .filter(
            batch__school=school,
            status=EnrollmentStatus.ENROLLED,
        )
    )

    if enrollment_ids:
        lock_queryset = lock_queryset.filter(
            id__in=enrollment_ids
        )

    elif student_ids:
        lock_queryset = lock_queryset.filter(
            student_id__in=student_ids
        )

    else:
        if batch_id is None:
            raise ValidationError({
                "selection": [
                    (
                        "Provide student_ids, "
                        "enrollment_ids, or batch_id."
                    )
                ]
            })

        lock_queryset = lock_queryset.filter(
            batch_id=batch_id
        )

        if academic_class_id is not None:
            lock_queryset = lock_queryset.filter(
                academic_class_id=academic_class_id
            )

        if section_id is not None:
            lock_queryset = lock_queryset.filter(
                section_id=section_id
            )

    # Lock only StudentEnrollments rows.
    # Do not join nullable section while applying FOR UPDATE.
    locked_enrollment_ids = list(
        lock_queryset
        .order_by(
            "academic_class_id",
            "section_id",
            "student_id",
            "id",
        )
        .values_list(
            "id",
            flat=True,
        )
    )

    if not locked_enrollment_ids:
        raise ValidationError({
            "selection": [
                (
                    "No active enrollments "
                    "matched the request."
                )
            ]
        })

    # Load related records after the base enrollment rows are locked.
    # This query remains inside the same transaction.
    enrollments = list(
        StudentEnrollments.objects
        .select_related(
            "student",
            "batch",
            "batch__school",
            "academic_class",
            "section",
        )
        .filter(
            id__in=locked_enrollment_ids
        )
        .order_by(
            "academic_class__name",
            "section__name",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student_id",
            "id",
        )
    )

    if enrollment_ids:
        requested_enrollment_ids = {
            str(value)
            for value in enrollment_ids
        }

        found_enrollment_ids = {
            str(enrollment.id)
            for enrollment in enrollments
        }

        missing_enrollment_ids = sorted(
            requested_enrollment_ids
            - found_enrollment_ids
        )

        if missing_enrollment_ids:
            raise ValidationError({
                "enrollment_ids": [
                    (
                        "No active enrollment found for: "
                        + ", ".join(
                            missing_enrollment_ids
                        )
                    )
                ]
            })

    if student_ids:
        requested_student_ids = {
            str(value)
            for value in student_ids
        }

        found_student_ids = {
            str(enrollment.student_id)
            for enrollment in enrollments
        }

        missing_student_ids = sorted(
            requested_student_ids
            - found_student_ids
        )

        if missing_student_ids:
            raise ValidationError({
                "student_ids": [
                    (
                        "No active enrollment found for: "
                        + ", ".join(
                            missing_student_ids
                        )
                    )
                ]
            })

        enrollment_counts: dict[str, int] = {}

        for enrollment in enrollments:
            student_key = str(
                enrollment.student_id
            )

            enrollment_counts[student_key] = (
                enrollment_counts.get(
                    student_key,
                    0,
                )
                + 1
            )

        ambiguous_student_ids = sorted(
            student_id
            for student_id, count
            in enrollment_counts.items()
            if count > 1
        )

        if ambiguous_student_ids:
            raise ValidationError({
                "student_ids": [
                    (
                        "Some students have multiple "
                        "active enrollments. Use "
                        "enrollment_ids for: "
                        + ", ".join(
                            ambiguous_student_ids
                        )
                    )
                ]
            })

    results = []

    for enrollment in enrollments:
        try:
            # Each invoice gets an individual savepoint.
            # One invalid student will not roll back successful invoices.
            with transaction.atomic():
                invoice, created = generate_invoice(
                    school=school,
                    enrollment=enrollment,
                    period_start=period_start,
                    period_end=period_end,
                    actor=actor,
                    invoice_date=invoice_date,
                    due_date=due_date,
                    apply_advance=apply_advance,
                    notes=notes,
                )

            results.append({
                "enrollment": enrollment,
                "invoice": invoice,
                "created": created,
                "error": None,
            })

        except ValidationError as exc:
            results.append({
                "enrollment": enrollment,
                "invoice": None,
                "created": False,
                "error": exc.detail,
            })

    return results