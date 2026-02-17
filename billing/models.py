from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

class Billing(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
    ]

    PAYMENT_CHOICES = [
        ("cash", "Cash"),
        ("esewa", "Esewa"),
        ("khalti", "Khalti"),
        ("bank_transfer", "Bank Transfer"),
    ]

    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="billings",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    inwords = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        null=True,
        blank=True,
    )

    receipt_number = models.CharField(max_length=50, unique=True)

    received_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="received_billings",
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def clean(self):
        # If paid, require payment_method
        if self.status == "paid" and not self.payment_method:
            raise ValidationError({"payment_method": "Payment method is required when status is paid."})

    def __str__(self):
        return f"Billing for {self.student} - {self.amount} ({self.status})"
