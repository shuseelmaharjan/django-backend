# enrollment/models.py
import uuid
from django.db import models
from django.utils import timezone

class StudentEnrollment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    academic_class = models.ForeignKey(
        "academics.AcademicClass",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollments",
    )

    roll_no = models.CharField(max_length=30, blank=True, default="")
    symbol_no = models.CharField(max_length=30, blank=True, default="")

    enrolled_on = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                name="uq_student_academic_year_enrollment",
            )
        ]
        indexes = [
            models.Index(fields=["school_id", "academic_year", "academic_class", "section"]),
            models.Index(fields=["student", "is_active"]),
        ]

    def __str__(self):
        sec = self.section.name if self.section else "-"
        return f"{self.student.user.email} -> {self.academic_year.name} {self.academic_class.code}/{sec}"


class PromotionLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="promotion_logs")

    from_enrollment = models.ForeignKey(
        StudentEnrollment, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    to_enrollment = models.ForeignKey(
        StudentEnrollment, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    promoted_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    promoted_at = models.DateTimeField(auto_now_add=True)
    remarks = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"Promotion({self.student.user.email})"
