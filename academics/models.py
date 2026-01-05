import uuid
from django.db import models
from django.db.models import Q


class AcademicYear(models.Model):
    """
    Example:
      2080-2081
      2024-2025
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()

    is_active = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school_id"],
                condition=Q(is_active=True),
                name="uq_school_one_active_academic_year",
            ),
            models.UniqueConstraint(fields=["school_id", "name"], name="uq_school_year_name"),
        ]
    def __str__(self):
        return f"{self.name}"


class AcademicClass(models.Model):
    """
    Represents Grade / Level / Course
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="classes"
    )

    code = models.CharField(max_length=50)   # e.g. "10", "BSc-CSIT-1"
    name = models.CharField(max_length=100)  # e.g. "Grade 10", "BSc CSIT 1st Year"
    order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("academic_year", "code")
        ordering = ["order"]

    def __str__(self):
        return self.name


class Section(models.Model):
    """
    Section within a class.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    academic_class = models.ForeignKey(
        AcademicClass,
        on_delete=models.CASCADE,
        related_name="sections"
    )

    name = models.CharField(max_length=20)  # A, B, Science, Morning
    capacity = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("academic_class", "name")

    def __str__(self):
        return f"{self.academic_class.name} - {self.name}"
