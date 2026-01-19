# academics/models.py
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class AcademicYear(models.Model):
    """
    Academic year per school.
    Example labels:
      - "2081/82"
      - "2025-2026"
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="academic_years",
        db_index=True,
    )

    label = models.CharField(max_length=30)  # e.g. "2081/82"
    start_date = models.DateField()
    end_date = models.DateField()

    is_current = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "label"], name="uq_school_year_label"),
        ]
        indexes = [
            models.Index(fields=["school", "is_current"]),
            models.Index(fields=["school", "start_date", "end_date"]),
        ]

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must be after start date."})

    def __str__(self):
        return f"{self.school.code} - {self.label}"


class AcademicClass(models.Model):
    """
    A class/grade level in a school.
    Examples:
      - Grade 1
      - Class 10
      - Nursery
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="classes",
        db_index=True,
    )

    # Display name
    name = models.CharField(max_length=80)  # e.g. "Grade 10", "Nursery"

    # Optional ordering numeric (useful for sorting)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uq_school_class_name"),
        ]
        indexes = [
            models.Index(fields=["school", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.school.code} - {self.name}"


class Section(models.Model):
    """
    A section inside a class (A/B/C, Red/Blue, etc.)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="sections",
        db_index=True,
    )

    academic_class = models.ForeignKey(
        AcademicClass,
        on_delete=models.CASCADE,
        related_name="sections",
        db_index=True,
    )

    name = models.CharField(max_length=30)  # e.g. "A", "B", "Science", "Red"
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["academic_class", "name"], name="uq_class_section_name"),
        ]
        indexes = [
            models.Index(fields=["school", "academic_class"]),
            models.Index(fields=["academic_class", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.academic_class.name} - {self.name}"
