import uuid
from django.db import models
from django.core.exceptions import ValidationError


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
