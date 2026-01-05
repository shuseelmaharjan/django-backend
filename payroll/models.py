import uuid
from decimal import Decimal
from django.db import models
from common.constants import SalaryComponentType, PayrollStatus

class SalaryComponent(models.Model):
    """
    Defines component types:
      - Basic
      - Grade
      - Allowance (transport, meals)
      - PF/SSF Deduction
      - Tax
      - Loan
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=120)

    component_type = models.CharField(max_length=20, choices=SalaryComponentType.choices, db_index=True)

    is_taxable = models.BooleanField(default=True)     # for future tax calc
    is_recurring = models.BooleanField(default=True)   # monthly by default
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class StaffSalaryStructure(models.Model):
    """
    One active salary structure per staff (can version later).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.CASCADE,
        related_name="salary_structures"
    )

    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["staff", "is_active"]),
        ]

    def __str__(self):
        return f"SalaryStructure({self.staff.user.email})"


class StaffSalaryLine(models.Model):
    """
    Salary breakdown lines (earning/deduction) for a staff structure.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    structure = models.ForeignKey(
        StaffSalaryStructure,
        on_delete=models.CASCADE,
        related_name="lines"
    )

    component = models.ForeignKey(SalaryComponent, on_delete=models.PROTECT)

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["structure", "component"], name="uq_structure_component")
        ]

    def __str__(self):
        return f"{self.component.code} - {self.amount}"


class PayrollRun(models.Model):
    """
    Monthly payroll run for a school.
    Example: 2081-05 or 2025-12
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)

    year = models.PositiveIntegerField(db_index=True)
    month = models.PositiveSmallIntegerField(db_index=True)  # 1..12

    status = models.CharField(max_length=20, choices=PayrollStatus.choices, default=PayrollStatus.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school_id", "year", "month"], name="uq_payroll_run_month")
        ]

    def __str__(self):
        return f"PayrollRun({self.school_id} - {self.year}/{self.month})"


class StaffPayroll(models.Model):
    """
    Result per staff for a PayrollRun (payslip summary).
    Attendance-based deductions can be applied here.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payrolls")
    staff = models.ForeignKey("staff.StaffProfile", on_delete=models.CASCADE, related_name="payrolls")

    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=20, choices=PayrollStatus.choices, default=PayrollStatus.GENERATED)

    # Optional: attach payslip file
    payslip_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "staff"], name="uq_run_staff_payroll")
        ]
        indexes = [
            models.Index(fields=["run", "status"]),
        ]

    def __str__(self):
        return f"{self.staff.user.email} - {self.run.year}/{self.run.month}"


class StaffPayrollLine(models.Model):
    """
    Line items for payslip (earnings/deductions).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payroll = models.ForeignKey(StaffPayroll, on_delete=models.CASCADE, related_name="lines")
    component = models.ForeignKey(SalaryComponent, on_delete=models.PROTECT)

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payroll", "component"], name="uq_payroll_component")
        ]
