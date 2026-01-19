# fees/models.py
import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class FeeFrequency(models.TextChoices):
    ONE_TIME = "one_time", _("One-time")
    MONTHLY = "monthly", _("Monthly")
    QUARTERLY = "quarterly", _("Quarterly")
    TERM = "term", _("Term")
    ANNUAL = "annual", _("Annual")
    ON_EVENT = "on_event", _("On Event")  # exams, trips, etc.


class FeeTrigger(models.TextChoices):
    ENROLLMENT = "enrollment", _("On Enrollment")
    PROMOTION = "promotion", _("On Promotion")
    EXAM = "exam", _("On Exam")
    CUSTOM = "custom", _("Custom / Manual")


class FeeType(models.Model):
    """
    Configurable fee heads per school (Admission, Annual, Exam, Lab, Library, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="fee_types")

    code = models.SlugField(max_length=60)   # e.g. admission_fee, exam_fee
    name = models.CharField(max_length=120)  # e.g. "Admission Fee"
    description = models.CharField(max_length=255, blank=True, default="")

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], name="uq_school_feetype_code")
        ]
        indexes = [
            models.Index(fields=["school", "is_active"]),
        ]

    def __str__(self):
        return f"{self.school.code}: {self.name}"


class FeePlan(models.Model):
    """
    A versioned fee configuration for a school.
    You can create multiple plans (per academic year, per grade/class, etc.)
    and switch which one is active.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="fee_plans")

    name = models.CharField(max_length=120)  # e.g. "FY 2081/82 - Grade 10"
    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.PROTECT, null=True, blank=True)

    # Optional scoping (if you want grade/class-wise fee plans)
    academic_class = models.ForeignKey("academics.AcademicClass", on_delete=models.PROTECT, null=True, blank=True)

    # Effective window (supports mid-year change)
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "is_active", "effective_from"]),
        ]

    def __str__(self):
        return f"{self.school.code}: {self.name}"


class FeePlanItem(models.Model):
    """
    Each row is one fee head + amount and how it should be charged.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    plan = models.ForeignKey(FeePlan, on_delete=models.CASCADE, related_name="items")
    fee_type = models.ForeignKey(FeeType, on_delete=models.PROTECT, related_name="plan_items")

    amount = models.DecimalField(max_digits=12, decimal_places=2, default="0.00")

    frequency = models.CharField(
        max_length=20,
        choices=FeeFrequency.choices,
        default=FeeFrequency.ONE_TIME,
        db_index=True,
    )

    trigger = models.CharField(
        max_length=20,
        choices=FeeTrigger.choices,
        default=FeeTrigger.CUSTOM,
        db_index=True,
    )

    # If it’s monthly, you can set months_count, etc. (optional)
    meta = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "fee_type"], name="uq_plan_feetype")
        ]
        indexes = [
            models.Index(fields=["plan", "is_active"]),
            models.Index(fields=["frequency", "trigger"]),
        ]

    def __str__(self):
        return f"{self.plan.name}: {self.fee_type.name} ({self.amount})"
