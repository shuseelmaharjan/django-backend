#academics/models.py
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q

class EnrollmentStatus(models.TextChoices):
    ENROLLED = "enrolled", "Enrolled"
    DROPPED = "dropped", "Dropped"
    GRADUATED = "graduated", "Graduated"
    SUSPENDED = "suspended", "Suspended"
    ALUMNI = "alumni", "Alumni"


class AcademicClass(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    batch = models.ForeignKey(
        "batch.AcademicBatch",
        on_delete=models.CASCADE,
        related_name="classes",
        db_index=True,
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=80)
    sort_order = models.PositiveSmallIntegerField(default=0)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["batch", "name"], name="uq_batch_class_name"),
        ]
        indexes = [
            models.Index(fields=["batch", "sort_order"]),
            models.Index(fields=["batch", "is_active"]),
        ]
        ordering = ["sort_order", "name"]

    def clean(self):
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": ["Name is required."]})

    def __str__(self):
        # batch is nullable, so keep safe
        if not self.batch_id:
            return self.name
        return f"{self.batch.school.code} - {self.batch.name} - {self.name}"


class Section(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    academic_class = models.ForeignKey(
        AcademicClass,
        on_delete=models.CASCADE,
        related_name="sections",
        db_index=True,
    )

    name = models.CharField(max_length=30)
    sort_order = models.PositiveSmallIntegerField(default=0)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["academic_class", "name"], name="uq_class_section_name"),
        ]
        indexes = [
            models.Index(fields=["academic_class", "sort_order"]),
            models.Index(fields=["academic_class", "is_active"]),
        ]
        ordering = ["sort_order", "name"]

    def clean(self):
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": ["Name is required."]})

    def __str__(self):
        return f"{self.academic_class.name} - {self.name}"

# class SubjectEnrollments(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     batch = models.ForeignKey(
#         "batch.AcademicBatch",
#         on_delete=models.CASCADE,
#         related_name="subject_enrollments",
#         db_index=True,
#     )
#     teacher = models.ForeignKey(
#         "accounts.User",
#         on_delete=models.CASCADE,
#         related_name="subject_enrollments",
#         db_index=True,
#     )
#     subject = models.ForeignKey(
#         "subjects.Subject",
#         on_delete=models.CASCADE,
#         related_name="enrollments",
#         db_index=True,
#     )
#     academic_class = models.ForeignKey(
#         "academics.AcademicClass",
#         on_delete=models.CASCADE,
#         related_name="subject_enrollments",
#         db_index=True,
#     )
#     section = models.ForeignKey(
#         "academics.Section",
#         on_delete=models.CASCADE,
#         related_name="subject_enrollments",
#         db_index=True,
#         null=True,
#         blank=True,
#     )
#     enrolled_at = models.DateTimeField(auto_now_add=True)
#     credit_hours = models.PositiveSmallIntegerField(default=0)
#     publication = models.TextField(blank=True, null=True)


class StudentEnrollments(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    batch = models.ForeignKey(
        "batch.AcademicBatch",
        on_delete=models.CASCADE,
        related_name="enrollments",
        db_index=True,
    )

    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="enrollments",
        db_index=True,
    )

    academic_class = models.ForeignKey(
        "academics.AcademicClass",
        on_delete=models.CASCADE,
        related_name="enrollments",
        db_index=True,
    )

    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.CASCADE,
        related_name="enrollments",
        db_index=True,
        null=True,
        blank=True,
    )

    enrolled_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ENROLLED,
        db_index=True,
    )

    class Meta:
        constraints = [
            # Student can't enroll in same class twice in same batch
            models.UniqueConstraint(
                fields=["batch", "student", "academic_class"],
                name="uq_batch_student_class_enrollment",
            ),
            # If section is provided, student can't enroll in same section twice in same batch
            models.UniqueConstraint(
                fields=["batch", "student", "section"],
                condition=Q(section__isnull=False),
                name="uq_batch_student_section_enrollment",
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "academic_class", "section"]),
            models.Index(fields=["batch", "student"]),
            models.Index(fields=["status"]),
        ]

    def clean(self):
        # batch must match academic_class.batch
        if self.academic_class_id and self.batch_id:
            if self.academic_class.batch_id != self.batch_id:
                raise ValidationError({"batch": ["Batch must match the academic class batch."]})

        # section must belong to academic_class
        if self.section_id and self.academic_class_id:
            if self.section.academic_class_id != self.academic_class_id:
                raise ValidationError({"section": ["Section must belong to the selected class."]})

    def __str__(self):
        return f"{self.student_id} -> {self.academic_class_id} ({self.batch_id})"