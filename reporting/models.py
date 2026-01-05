# reporting/models.py
import uuid
from django.db import models

class ReportJobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


class ReportTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.CharField(max_length=64, db_index=True)

    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True, default="")

    config_schema = models.JSONField(default=dict, blank=True)  # optional UI schema
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("school_id", "code")

    def __str__(self):
        return self.name


class ReportJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.CharField(max_length=64, db_index=True)

    requested_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT, related_name="jobs")

    filters = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=ReportJobStatus.choices, default=ReportJobStatus.QUEUED, db_index=True)

    output_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
