import uuid
from django.db import models

class School(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=50, unique=True)  # e.g. "greenvalley"
    name = models.CharField(max_length=150)

    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    logo_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    timezone = models.CharField(max_length=64, default="Asia/Kathmandu")
    currency = models.CharField(max_length=10, default="NPR")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Campus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="campuses")
    name = models.CharField(max_length=120)

    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("school", "name")

    def __str__(self):
        return f"{self.school.name} - {self.name}"


class SchoolSetting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="settings")

    # Billing numbering
    invoice_prefix = models.CharField(max_length=20, default="INV")
    receipt_prefix = models.CharField(max_length=20, default="RCPT")
    fiscal_year_label = models.CharField(max_length=30, blank=True, default="")

    # Late fee policy (simple)
    late_fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    late_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default="0.00")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings({self.school.code})"
