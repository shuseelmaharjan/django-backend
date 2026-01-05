# communication/models.py
import uuid
from django.db import models
from django.utils import timezone

class Notice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.CharField(max_length=64, db_index=True)

    title = models.CharField(max_length=200)
    body = models.TextField()

    target_type = models.CharField(max_length=30, db_index=True)  # SCHOOL/CLASS/SECTION/STUDENT/STAFF
    target_id = models.CharField(max_length=64, db_index=True, default="*")

    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def publish(self):
        self.published_at = timezone.now()
        self.save(update_fields=["published_at"])

    def __str__(self):
        return self.title


class MessageLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.CharField(max_length=64, db_index=True)

    channel = models.CharField(max_length=20, db_index=True)  # sms/email/push
    to = models.CharField(max_length=120, db_index=True)
    provider = models.CharField(max_length=40, blank=True, default="")

    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, db_index=True, default="queued")

    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
