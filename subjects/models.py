# subjects/models.py
import uuid

from django.db import models

class SubjectStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    DELETED = "deleted", "Deleted"

# Create your models here.
class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=SubjectStatus.choices,
        default=SubjectStatus.ACTIVE,
        db_index=True,
    )
    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["code"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"
