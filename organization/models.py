import uuid
from django.db import models
from django. core.exceptions import ValidationError
from django.conf import settings


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

    def clean(self):
        """Ensure only one active school exists and validate phone"""
        from utils.phone_validator import clean_and_validate_phone

        if self.is_active:
            active_schools = School.objects.filter(is_active=True)
            if self.pk:
                active_schools = active_schools.exclude(pk=self.pk)
            if active_schools.exists():
                raise ValidationError("Only one school can be active at a time.")

        # Validate and format phone
        if self.phone:
            self.phone = clean_and_validate_phone(self.phone)


    def save(self, *args, **kwargs):
        self.full_clean()
        # If this school is being set to active, deactivate others
        if self.is_active:
            School.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class Campus(models. Model):
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

    def clean(self):
        """Ensure only one active campus per school and validate phone"""
        from utils.phone_validator import clean_and_validate_phone

        if self.is_active:
            active_campuses = Campus.objects.filter(
                school=self.school, is_active=True
            )
            if self.pk:
                active_campuses = active_campuses.exclude(pk=self.pk)
            if active_campuses.exists():
                raise ValidationError("Only one campus can be active per school at a time.")

        # Validate and format phone
        if self.phone:
            self.phone = clean_and_validate_phone(self.phone)

    def save(self, *args, **kwargs):
        self.full_clean()
        # If this campus is being set to active, deactivate others for this school
        if self.is_active:
            Campus.objects.filter(school=self.school).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class SchoolSetting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid. uuid4, editable=False)
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="settings")

    # Billing numbering
    invoice_prefix = models.CharField(max_length=20, default="INV")
    receipt_prefix = models.CharField(max_length=20, default="RCPT")
    fiscal_year_label = models.CharField(max_length=30, blank=True, default="")

    # Late fee policy (simple)
    late_fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    late_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default="0.00")

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings({self.school.code})"

    def clean(self):
        """Ensure only one active school setting exists"""
        if self. is_active:
            active_settings = SchoolSetting.objects.filter(is_active=True)
            if self.pk:
                active_settings = active_settings.exclude(pk=self.pk)
            if active_settings.exists():
                raise ValidationError("Only one school setting can be active at a time.")

    def save(self, *args, **kwargs):
        self.full_clean()
        # If this setting is being set to active, deactivate others
        if self.is_active:
            SchoolSetting.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)