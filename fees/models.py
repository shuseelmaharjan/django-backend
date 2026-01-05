import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from common.constants import FeeFrequency, TargetType, FeeCalcType, ChargeStatus


class FeeHead(models.Model):
    """
    WHAT the fee is: tuition, admission, bus, exam, library, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.SlugField(max_length=60)
    school_id = models.CharField(max_length=64, db_index=True, default="")
    name = models.CharField(max_length=120)

    frequency = models.CharField(
        max_length=20,
        choices=FeeFrequency.choices,
        default=FeeFrequency.ONE_TIME,
        db_index=True
    )

    is_optional = models.BooleanField(default=False)  # bus/hostel optional
    is_refundable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("school_id", "code")

    def __str__(self):
        return self.name



class FeePlan(models.Model):
    """
    A plan groups all fee rules for a school and academic year.
    Example: "School-1 Fee Plan 2081"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="fee_plans"
    )

    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("school_id", "academic_year", "name")

    def __str__(self):
        return self.name


class FeeRule(models.Model):
    """
    A rule defines:
      - target (class/section/student or whole school)
      - fee head
      - calculation (fixed or per unit)
      - amount
      - schedule / months / terms / exam sessions
      - optional rules (bus applies only if student opted in)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    plan = models.ForeignKey(FeePlan, on_delete=models.CASCADE, related_name="rules")

    fee_head = models.ForeignKey(FeeHead, on_delete=models.PROTECT, related_name="rules")

    target_type = models.CharField(max_length=20, choices=TargetType.choices, db_index=True)
    target_id = models.CharField(max_length=64, db_index=True, default="*")
    # target_id examples:
    #   - "*" means all within that target_type scope
    #   - for CLASS: academic_class_id
    #   - for SECTION: section_id
    #   - for STUDENT: student_profile_id

    calc_type = models.CharField(max_length=20, choices=FeeCalcType.choices, default=FeeCalcType.FIXED)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # for PER_UNIT calc:
    unit_name = models.CharField(max_length=50, blank=True, default="")  # "credit", "subject", "trip"
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # Scheduling:
    # We keep it simple and flexible:
    # - months: "1,2,3,4,5,6,7,8,9,10,11,12" for monthly patterns
    # - term_codes: "T1,T2" etc
    # - exam_codes: "E1,E2" etc
    months_csv = models.CharField(max_length=64, blank=True, default="")
    term_codes_csv = models.CharField(max_length=120, blank=True, default="")
    exam_codes_csv = models.CharField(max_length=120, blank=True, default="")

    # Optional rules
    is_mandatory = models.BooleanField(default=True)

    # Rule validity
    active_from = models.DateField(null=True, blank=True)
    active_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    priority = models.PositiveIntegerField(default=100)  # lower = higher priority for overrides (section overrides class etc.)

    class Meta:
        indexes = [
            models.Index(fields=["plan", "target_type", "target_id"]),
            models.Index(fields=["fee_head", "is_active"]),
        ]

    def __str__(self):
        return f"{self.plan.name} | {self.fee_head.code} | {self.target_type}:{self.target_id}"

    def is_valid_on(self, on_date):
        if not self.is_active:
            return False
        if self.active_from and on_date < self.active_from:
            return False
        if self.active_to and on_date > self.active_to:
            return False
        return True


# ---------- Student Layer (Preferences / Overrides) ----------

class StudentFeeOption(models.Model):
    """
    Stores student's opt-ins (bus/hostel etc) and unit counts (subjects/credits/trips).
    This avoids hacking optional fees into StudentProfile.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="fee_options"
    )

    fee_head = models.ForeignKey(FeeHead, on_delete=models.PROTECT)

    is_enabled = models.BooleanField(default=True)

    # For PER_UNIT fees: e.g. number of subjects, credits, trips, etc
    units = models.PositiveIntegerField(default=0)

    # optional supporting doc (e.g. scholarship letter)
    support_document = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ("student", "fee_head")

    def __str__(self):
        return f"{self.student.user.email} - {self.fee_head.code}"


class StudentFeeOverride(models.Model):
    """
    Per-student override:
      - discount (percentage or fixed)
      - waive a specific fee
      - override amount
    Nepal use case:
      - scholarship discount on tuition
      - sibling discount
      - staff child discount
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="fee_overrides"
    )

    fee_head = models.ForeignKey(FeeHead, on_delete=models.PROTECT)

    # Overrides
    override_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    is_waived = models.BooleanField(default=False)

    reason = models.CharField(max_length=200, blank=True, default="")

    # optional proof file
    proof_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("student", "fee_head")

    def __str__(self):
        return f"Override({self.student.user.email} - {self.fee_head.code})"


# ---------- Transaction Layer (Generated Charges) ----------

class StudentCharge(models.Model):
    """
    Generated payable items per student, per period.
    Examples:
      - Tuition (month=5)
      - Annual fee (yearly)
      - Exam fee (exam_code=E1)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="charges"
    )
    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.CASCADE)

    fee_head = models.ForeignKey(FeeHead, on_delete=models.PROTECT)

    # period identifiers (use what applies)
    month = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-12
    term_code = models.CharField(max_length=30, blank=True, default="")
    exam_code = models.CharField(max_length=30, blank=True, default="")

    base_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=20, choices=ChargeStatus.choices, default=ChargeStatus.PENDING)

    # For auditability: which rule produced it
    generated_from_rule = models.ForeignKey(
        FeeRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_charges"
    )

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "fee_head", "status"]),
            models.Index(fields=["academic_year", "month"]),
            models.Index(fields=["academic_year", "term_code"]),
            models.Index(fields=["academic_year", "exam_code"]),
        ]
        constraints = [
            # prevent duplicates (same head + same period)
            models.UniqueConstraint(
                fields=["student", "academic_year", "fee_head", "month", "term_code", "exam_code"],
                name="uq_student_charge_period"
            )
        ]

    def __str__(self):
        period = self.term_code or self.exam_code or (f"m{self.month}" if self.month else "one-time")
        return f"{self.student.user.email} - {self.fee_head.code} ({period})"
