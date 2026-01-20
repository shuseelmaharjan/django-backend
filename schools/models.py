# schools/models.py
import uuid
from django.db import models
from django.core.exceptions import ValidationError


class School(models.Model):
    """
    Tenant model (1 school = 1 client for now).
    Owned by a principal user (client owner).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Public identifiers
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=150)

    # Ownership (principal / client owner)
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="owned_schools",
        help_text="Principal / client owner of this school",
    )

    # Contact
    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    # Branding
    logo_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    # Government / legal info (Nepal focused, optional)
    pan_number = models.CharField(max_length=40, blank=True, default="", db_index=True)
    registration_number = models.CharField(max_length=80, blank=True, default="", db_index=True)

    # Documents (UploadedFile pattern)
    pan_document_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="PAN document scan",
    )

    registration_document_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Registration document scan",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        """
        Validate & normalize phone.
        """
        from utils.phone_validator import clean_and_validate_phone

        if self.phone:
            self.phone = clean_and_validate_phone(self.phone)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class SchoolSetting(models.Model):
    """
    One-to-one settings per school.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school = models.OneToOneField(
        School,
        on_delete=models.CASCADE,
        related_name="settings",
    )

    invoice_prefix = models.CharField(max_length=20, default="INV")
    receipt_prefix = models.CharField(max_length=20, default="RCPT")
    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.PROTECT)

    # Fees / penalties (optional)
    late_fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    late_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default="0.00")

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings({self.school.code})"
