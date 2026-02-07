from django.db import models
from django.core.exceptions import ValidationError
from utils.dates import bs_to_ad


class AcademicBatch(models.Model):
    id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=100)

    start_date_bs = models.CharField(max_length=10)  # YYYY-MM-DD (BS)
    start_date_ad = models.DateField(editable=False)

    end_date_bs = models.CharField(max_length=10)  # YYYY-MM-DD (BS)
    end_date_ad = models.DateField(editable=False)

    is_active = models.BooleanField(default=False)

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="batches",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "is_active", "start_date_ad", "end_date_ad"]),
        ]
        ordering = ["-start_date_ad", "-id"]

    def clean(self):
        # Convert BS -> AD
        try:
            self.start_date_ad = bs_to_ad(self.start_date_bs)
        except ValidationError as e:
            raise ValidationError({"start_date_bs": e.messages})

        try:
            self.end_date_ad = bs_to_ad(self.end_date_bs)
        except ValidationError as e:
            raise ValidationError({"end_date_bs": e.messages})

        if self.start_date_ad and self.end_date_ad and self.start_date_ad > self.end_date_ad:
            raise ValidationError({"end_date_bs": ["end_date must be >= start_date."]})

        # Overlap rule ONLY against ACTIVE batches in same school
        # overlap condition: existing.start <= new.end AND existing.end >= new.start
        qs = self.__class__.objects.filter(school=self.school)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.filter(start_date_ad__lte=self.end_date_ad, end_date_ad__gte=self.start_date_ad).exists():
            raise ValidationError(
                {"non_field_errors": [
                    "A batch already exists that overlaps this date range."
                ]}
            )

    def save(self, *args, **kwargs):
        self.full_clean()  # runs clean() and field validations
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.school.code})"
