# authx/models.py
import uuid
from django.db import models
from django.utils import timezone


class ClientType(models.TextChoices):
    WEB = "web", "Web"
    MOBILE = "mobile", "Mobile"


class UserSession(models.Model):
    """
    Tracks login sessions on the server.
    One session maps to one refresh token (jti).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="sessions",
    )

    # Client classification
    client_type = models.CharField(
        max_length=16,
        choices=ClientType.choices,
        default=ClientType.WEB,
        db_index=True,
    )

    # Token binding
    refresh_jti = models.CharField(max_length=64, unique=True, db_index=True)
    refresh_expires_at = models.DateTimeField(db_index=True)

    # -------- Device / environment --------
    device_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Mobile device ID or browser fingerprint",
    )
    device_name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="e.g. iPhone 14, Chrome on Windows",
    )
    os_name = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Android, iOS, Windows, macOS",
    )
    os_version = models.CharField(
        max_length=32,
        blank=True,
        default="",
    )
    app_version = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Mobile/Web app version",
    )

    # -------- Network --------
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    # -------- Lifecycle --------
    created_at = models.DateTimeField(auto_now_add=True)   # login time
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "client_type"]),
            models.Index(fields=["revoked_at"]),
            models.Index(fields=["last_seen_at"]),
        ]

    @property
    def is_active(self) -> bool:
        if self.revoked_at:
            return False
        return timezone.now() < self.refresh_expires_at

    def touch(self):
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at"])

    def revoke(self):
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])
