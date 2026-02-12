import uuid
from django.db import models
from django.core.exceptions import ValidationError


class EcaActivityStatus(models.TextChoices):
    active = "active", "Active"
    inactive = "inactive", "Inactive"
    archived = "archived", "Archived"
    deleted = "deleted", "Deleted"


class EcaActivities(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="eca_activities",
    )

    fees = models.ForeignKey(
        "fees.FeeStructure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eca_activities",
    )

    status = models.CharField(
        max_length=20,
        choices=EcaActivityStatus.choices,
        default=EcaActivityStatus.active,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["school", "status", "name"]),
        ]

    def clean(self):
        qs = EcaActivities.objects.filter(school=self.school).exclude(status=EcaActivityStatus.deleted)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.filter(name__iexact=self.name.strip()).exists():
            raise ValidationError({"name": ["An ECA activity with this name already exists."]})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
