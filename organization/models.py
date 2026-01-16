import uuid
from django.db import models
from django.core.exceptions import ValidationError

class School(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=50, unique=True)
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

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def clean(self):
        """
        Validate and normalize phone.
        (REMOVED: only-one-active-school restriction)
        """
        from utils.phone_validator import clean_and_validate_phone

        if self.phone:
            self.phone = clean_and_validate_phone(self.phone)

    def save(self, *args, **kwargs):
        # keep model-level validation
        self.full_clean()
        super().save(*args, **kwargs)


class SchoolSetting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # One setting per school (still true because OneToOne)
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="settings")

    invoice_prefix = models.CharField(max_length=20, default="INV")
    receipt_prefix = models.CharField(max_length=20, default="RCPT")
    fiscal_year_label = models.CharField(max_length=30, blank=True, default="")

    late_fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    late_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default="0.00")

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings({self.school.code})"