from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from fees.models import FeeRule, StudentCharge, FeeCalcType
from students.models import StudentProfile
from enrollment.models import StudentEnrollment


def _to_decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


@transaction.atomic
def generate_charges(
    *,
    school_id: str,
    academic_year_id,
    month: int | None = None,
    term_code: str = "",
    exam_code: str = "",
    academic_class_id=None,
    section_id=None,
) -> dict:
    """
    Generate StudentCharge rows from active FeeRules for matching scope.

    Conditions enforced:
    - student must have an active enrollment in that academic year
    - rules must be active and valid on today's date
    - unique constraint prevents duplicates per (student, year, head, month, term, exam)

    Returns summary counts.
    """
    today = timezone.now().date()

    # Eligible students: active enrollments in that year (optionally filtered by class/section)
    enr_qs = StudentEnrollment.objects.select_related("student").filter(
        school_id=school_id,
        academic_year_id=academic_year_id,
        is_active=True,
    )
    if academic_class_id:
        enr_qs = enr_qs.filter(academic_class_id=academic_class_id)
    if section_id:
        enr_qs = enr_qs.filter(section_id=section_id)

    enrollments = list(enr_qs)
    student_ids = [e.student_id for e in enrollments]

    if not student_ids:
        return {"created": 0, "skipped": 0, "students": 0}

    # Active rules for that academic year (plan->year is implicit via plan relation)
    # Your FeeRule has plan FK; FeePlan has academic_year FK.
    rules = FeeRule.objects.select_related("plan", "fee_head").filter(
        plan__academic_year_id=academic_year_id,
        plan__school_id=school_id,
        is_active=True,
    )

    created = 0
    skipped = 0

    for enr in enrollments:
        student = enr.student

        for rule in rules:
            if not rule.is_valid_on(today):
                continue

            # --- scope matching (rule target) ---
            ttype = rule.target_type
            tid = rule.target_id

            # "*" matches all inside that scope.
            # For school scope: TargetType.SCHOOL with "*"
            # For class: tid is academic_class_id
            # For section: tid is section_id
            # For student: tid is student_profile_id
            if ttype == "school":
                if tid != "*":
                    continue
            elif ttype == "class":
                if tid != "*" and str(enr.academic_class_id) != str(tid):
                    continue
            elif ttype == "section":
                if tid != "*" and str(enr.section_id or "") != str(tid):
                    continue
            elif ttype == "student":
                if tid != "*" and str(student.id) != str(tid):
                    continue
            else:
                continue

            # --- schedule matching ---
            if month is not None:
                months = [m.strip() for m in (rule.months_csv or "").split(",") if m.strip()]
                if months and str(month) not in months:
                    continue
            if term_code:
                terms = [t.strip() for t in (rule.term_codes_csv or "").split(",") if t.strip()]
                if terms and term_code not in terms:
                    continue
            if exam_code:
                exams = [e.strip() for e in (rule.exam_codes_csv or "").split(",") if e.strip()]
                if exams and exam_code not in exams:
                    continue

            # --- amount calculation ---
            base_amount = _to_decimal(rule.amount)
            discount_amount = Decimal("0.00")  # later apply overrides/options
            final_amount = base_amount - discount_amount

            # Create charge (unique constraint prevents duplicates)
            obj, was_created = StudentCharge.objects.get_or_create(
                student_id=student.id,
                academic_year_id=academic_year_id,
                fee_head_id=rule.fee_head_id,
                month=month,
                term_code=term_code or "",
                exam_code=exam_code or "",
                defaults={
                    "base_amount": base_amount,
                    "discount_amount": discount_amount,
                    "final_amount": final_amount,
                    "generated_from_rule": rule,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

    return {"created": created, "skipped": skipped, "students": len(student_ids)}
