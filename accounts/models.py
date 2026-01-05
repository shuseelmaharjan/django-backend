import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from common.constants import UserStatus, ScopeType

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", UserStatus.ACTIVE)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractUser):
    """
    Minimal but future-proof user model.
    - email login
    - status flag
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    username = models.CharField(max_length=150, unique=False, blank=True)
    email = models.EmailField(unique=True)

    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
        db_index=True,
    )

    phone = models.CharField(max_length=32, blank=True, default="")

    # if you want avatar/photo etc later:
    # avatar_file = models.ForeignKey("filehandler.UploadedFile", ...)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Role(models.Model):
    """
    Coarse role: Admin, Teacher, Student, Parent, Accountant, Coordinator, etc.
    Keep it simple now.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.CharField(max_length=64, db_index=True, default="*")
    code = models.SlugField(max_length=50)    # e.g. "admin", "teacher"
    name = models.CharField(max_length=80)

    is_system = models.BooleanField(default=False)  # lock core roles if you want

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school_id", "code"], name="uq_role_school_code"),
        ]

    def __str__(self):
        return self.name


class RoleAssignment(models.Model):
    """
    Assign a role to a user with a scope.
    Examples:
      - Teacher scoped to class=10A
      - Accountant scoped to school=XYZ
      - Admin scoped global
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey("accounts.Role", on_delete=models.PROTECT, related_name="assignments")

    scope_type = models.CharField(max_length=20, choices=ScopeType.choices, default=ScopeType.GLOBAL)
    scope_id = models.CharField(max_length=64, default="*")  # flexible string id, e.g. "school-1", "class-10A"

    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "scope_type", "scope_id"],
                name="uq_user_role_scope",
            )
        ]
        indexes = [
            models.Index(fields=["user", "role"]),
            models.Index(fields=["scope_type", "scope_id"]),
        ]

    def is_active(self, at=None) -> bool:
        at = at or timezone.now()
        if self.valid_from and at < self.valid_from:
            return False
        if self.valid_to and at > self.valid_to:
            return False
        return True

    def __str__(self):
        return f"{self.user.email} -> {self.role.code} ({self.scope_type}:{self.scope_id})"
