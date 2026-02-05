import uuid
from django.db import models
from django.core.exceptions import ValidationError


class AcademicClass(models.Model):
    """
    A class/grade level in a batch.
    Examples: Grade 1, Class 10, Nursery
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    batch = models.ForeignKey(
        "batch.AcademicBatch",
        on_delete=models.CASCADE,
        related_name="classes",
        db_index=True,
    )

    name = models.CharField(max_length=80)  # e.g. "Grade 10", "Nursery"
    sort_order = models.PositiveSmallIntegerField(default=0)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # unique class name inside a batch
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
        return f"{self.batch.school.code} - {self.batch.name} - {self.name}"


class Section(models.Model):
    """
    A section inside a class (A/B/C, Red/Blue, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    academic_class = models.ForeignKey(
        AcademicClass,
        on_delete=models.CASCADE,
        related_name="sections",
        db_index=True,
    )

    name = models.CharField(max_length=30)  # e.g. "A", "B", "Science", "Red"
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
