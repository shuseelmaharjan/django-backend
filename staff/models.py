import uuid
from django.db import models
from common.constants import StaffType, EmploymentStatus, StaffAttendanceStatus

class StaffProfile(models.Model):
    """
    Common staff profile for any employee.
    Covers Admin/Accountant/Coordinator/Teacher/etc.
    Teacher-specific data goes to TeacherProfile.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="staff_profile"
    )

    school_id = models.CharField(max_length=64, db_index=True)
    campus_id = models.CharField(max_length=64, db_index=True, blank=True, default="")

    staff_type = models.CharField(max_length=30, choices=StaffType.choices, db_index=True)

    employee_code = models.CharField(max_length=40, blank=True, default="", db_index=True)

    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
        db_index=True
    )

    joined_date = models.DateField(null=True, blank=True)

    # Nepal common IDs (optional)
    citizenship_no = models.CharField(max_length=80, blank=True, default="")
    pan_no = models.CharField(max_length=40, blank=True, default="")
    ssf_no = models.CharField(max_length=40, blank=True, default="")

    # Address (simple for staff; you can also normalize like StudentAddress if needed)
    permanent_address = models.CharField(max_length=255, blank=True, default="")
    temporary_address = models.CharField(max_length=255, blank=True, default="")

    # Documents (citizenship/pan/contract/etc.) via your UploadedFile pattern
    citizenship_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )
    contract_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.staff_type}"
    
class TeacherProfile(models.Model):
    """
    Only for staff who are teachers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    staff = models.OneToOneField(
        "staff.StaffProfile",
        on_delete=models.CASCADE,
        related_name="teacher_profile"
    )

    designation = models.CharField(max_length=120, blank=True, default="")  # e.g., "Senior Teacher"
    qualification = models.CharField(max_length=200, blank=True, default="")

    signature_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Teacher({self.staff.user.email})"


class TeacherAssignment(models.Model):
    """
    Assign a teacher to a class/section for an academic year.
    This is what powers:
      - attendance scope
      - grade scope
      - timetable scope
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="teacher_assignments"
    )

    academic_class = models.ForeignKey(
        "academics.AcademicClass",
        on_delete=models.CASCADE,
        related_name="teacher_assignments"
    )

    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="teacher_assignments"
    )

    # Optional if you add Subject model later
    subject_id = models.CharField(max_length=64, blank=True, default="")

    is_class_teacher = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["academic_year", "academic_class", "section"]),
            models.Index(fields=["teacher", "academic_year"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "academic_year", "academic_class", "section", "subject_id", "is_class_teacher"],
                name="uq_teacher_assignment"
            )
        ]

    def __str__(self):
        sec = self.section.name if self.section else "*"
        return f"{self.teacher.staff.user.email} -> {self.academic_class.name}/{sec}"


class StaffAttendance(models.Model):
    """
    One row per staff per day.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.CASCADE,
        related_name="attendance"
    )

    date = models.DateField(db_index=True)

    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=StaffAttendanceStatus.choices,
        default=StaffAttendanceStatus.PRESENT,
        db_index=True
    )

    remarks = models.CharField(max_length=255, blank=True, default="")

    marked_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff", "date"], name="uq_staff_attendance_day")
        ]
        indexes = [
            models.Index(fields=["date", "status"]),
        ]

    def __str__(self):
        return f"{self.staff.user.email} - {self.date} - {self.status}"