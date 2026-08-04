# accounts/models.py
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models import Q
from django.utils import timezone

from common.constants import UserStatus, UserRole
from common.models import SoftDeleteModel


def _gen_username_from_phone(phone: str) -> str:
    # simple default: "u_<last 8 digits>"
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    tail = digits[-8:] if len(digits) >= 8 else digits
    return f"u_{tail}" if tail else f"u_{uuid.uuid4().hex[:10]}"


def _next_registration_no_for_year(year: int) -> str:
    """
    Generates: YYYY-000001 (global sequence per year)
    If you want per-school sequence, we can scope it later.
    """
    prefix = f"{year}-"

    last = (
        User.objects.filter(is_deleted=False, registration_no__startswith=prefix)
        .order_by("-registration_no")
        .values_list("registration_no", flat=True)
        .first()
    )

    last_no = int(last.split("-")[1]) if last else 0
    return f"{year}-{last_no + 1:06d}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone number is required")

        try:
            from utils.phone_validator import clean_and_validate_phone

            phone = clean_and_validate_phone(phone)
        except Exception:
            phone = str(phone).strip()

        # ensure username exists (auto)
        extra_fields.setdefault("username", _gen_username_from_phone(phone))

        user = self.model(phone=phone, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", UserStatus.ACTIVE)
        extra_fields.setdefault("role", UserRole.SUPERADMIN)

        if not password:
            raise ValueError("Superadmin must have a password")

        return self.create_user(phone=phone, password=password, **extra_fields)


class User(SoftDeleteModel, AbstractUser):
    """
    Phone-based login user model.

    Supports:
    - phone as login (unique, required)
    - enum role
    - status lifecycle
    - first/middle/last name
    - profile picture (UploadedFile)
    - auto-generated unique username (not used for login)
    - permanent registration_no (symbol/registration id) generated once
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Phone is the login identifier
    phone = models.CharField(max_length=32, unique=True, db_index=True)

    # Email optional (not unique)
    email = models.EmailField(blank=True, default="")

    # Middle name (AbstractUser already provides first_name + last_name)
    middle_name = models.CharField(max_length=80, blank=True, default="")

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.OTHER,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
        db_index=True,
    )

    profile_picture_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    # make username unique if you're autogenerating it
    username = models.CharField(max_length=150, unique=True, blank=True, default="")

    registration_no = models.CharField(
        max_length=20,
        blank=True,
        default="",
        db_index=True,
        editable=False,  # 🔒 not editable in admin/forms
    )

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def clean(self):
        super().clean()
        if self.phone:
            try:
                from utils.phone_validator import clean_and_validate_phone

                self.phone = clean_and_validate_phone(self.phone)
            except Exception:
                self.phone = str(self.phone).strip()

    def save(self, *args, **kwargs):
        creating = self._state.adding

        # Make registration_no immutable (extra safety)
        if not creating and self.pk:
            old = User.objects.filter(pk=self.pk).values("registration_no").first()
            if old and old.get("registration_no") and self.registration_no != old["registration_no"]:
                self.registration_no = old["registration_no"]

        # Auto-generate username if missing
        if not self.username:
            base = _gen_username_from_phone(self.phone)
            candidate = base
            i = 1
            while User.objects.filter(username=candidate).exclude(pk=self.pk).exists():
                i += 1
                candidate = f"{base}_{i}"
            self.username = candidate

        # Keep Django admin expectation: superuser must be staff
        if self.is_superuser:
            self.is_staff = True

        super().save(*args, **kwargs)

        # If you want ONLY students to get it, uncomment the role condition below.
        if creating and not self.registration_no:
            # if self.role != UserRole.STUDENT:
            #     return

            with transaction.atomic():
                year = timezone.now().year
                prefix = f"{year}-"

                # lock "the latest row" for this year to avoid duplicates in concurrent requests
                (
                    User.objects.select_for_update()
                    .filter(is_deleted=False, registration_no__startswith=prefix)
                    .order_by("-registration_no")
                    .first()
                )

                reg = _next_registration_no_for_year(year)

                # write directly without triggering recursion / re-save loops
                User.objects.filter(pk=self.pk).update(registration_no=reg)
                self.registration_no = reg  # keep instance consistent

    def soft_delete(self, *args, **kwargs):
        self.status = UserStatus.DELETED
        self.is_active = False
        self.save(update_fields=["status", "is_active"])
        return super().soft_delete(*args, **kwargs)

    def __str__(self):
        full = " ".join([self.first_name, self.middle_name, self.last_name]).strip()
        return full or self.phone

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["phone"],
                condition=Q(is_deleted=False),
                name="uq_user_phone_alive",
            ),
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(is_deleted=False) & ~Q(email=""),
                name="uq_user_email_alive",
            ),
            models.UniqueConstraint(
                fields=["username"],
                condition=Q(is_deleted=False) & ~Q(username=""),
                name="uq_user_username_alive",
            ),
            models.UniqueConstraint(
                fields=["registration_no"],
                condition=Q(is_deleted=False) & ~Q(registration_no=""),
                name="uq_user_registration_no_alive",
            ),
        ]


class PasswordResetOTP(models.Model):
    """
    Stores OTP for password reset via email.

    Notes:
    - OTP is stored as a HASH (never plaintext).
    - After OTP is verified, we issue a reset_token (UUID) used to set a new password.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_otps",
    )

    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    # rate limiting / brute force protection
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)

    # status
    is_used = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    # issued after OTP verification
    reset_token = models.UUIDField(null=True, blank=True, db_index=True)
    reset_token_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "expires_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["reset_token", "reset_token_expires_at"]),
        ]

    @classmethod
    def default_expiry(cls) -> timezone.datetime:
        return timezone.now() + timedelta(minutes=10)

    @classmethod
    def default_reset_token_expiry(cls) -> timezone.datetime:
        return timezone.now() + timedelta(minutes=15)

    def expired(self) -> bool:
        return timezone.now() > self.expires_at

    def reset_token_expired(self) -> bool:
        return not self.reset_token_expires_at or timezone.now() > self.reset_token_expires_at

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])


class EmailChangeOTP(models.Model):
    """
    Verifies an email change through the user's existing email address.

    Flow:
    1. User submits the proposed new email.
    2. OTP is sent to the current/existing email.
    3. User verifies OTP.
    4. The user's email is changed to the pending new email.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_change_otps",
    )

    current_email = models.EmailField(db_index=True)
    new_email = models.EmailField(db_index=True)

    otp_hash = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)

    is_used = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "is_used", "expires_at"]),
            models.Index(fields=["current_email", "expires_at"]),
            models.Index(fields=["new_email", "expires_at"]),
        ]

    @classmethod
    def default_expiry(cls):
        return timezone.now() + timedelta(minutes=10)

    def expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])
