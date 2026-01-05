# filehandler/models.py
import uuid
from django.db import models
from django.conf import settings
from filehandler.constants import FileType
from filehandler.utils import upload_to
from filehandler.validators import detect_file_type, validate_upload

class UploadedFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER,
        db_index=True,
    )

    file = models.FileField(upload_to=upload_to)

    original_name = models.CharField(max_length=255, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)

    # You can keep temporary flag for cleanup jobs later
    is_temporary = models.BooleanField(default=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_files",
    )

    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["file_type"]),
            models.Index(fields=["uploaded_at"]),
        ]

    def __str__(self):
        return f"{self.file_type} - {self.original_name or self.file.name}"

    def clean(self):
        if not self.file:
            return

        self.original_name = self.original_name or getattr(self.file, "name", "")
        self.size_bytes = getattr(self.file, "size", 0)

        inferred = detect_file_type(self.original_name)

        # If not explicitly set, infer file_type
        if not self.file_type or self.file_type == FileType.OTHER:
            self.file_type = inferred

        validate_upload(self.file, file_type=self.file_type)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        storage = self.file.storage if self.file else None
        name = self.file.name if self.file else None
        super().delete(*args, **kwargs)
        if storage and name and storage.exists(name):
            storage.delete(name)
