# profiles/models.py
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

class Gender(models.TextChoices):
    MALE = "male", _("Male")
    FEMALE = "female", _("Female")
    OTHER = "other", _("Other")

class BloodGroup(models.TextChoices):
    A_POS = "A+", "A+"
    A_NEG = "A-", "A-"
    B_POS = "B+", "B+"
    B_NEG = "B-", "B-"
    AB_POS = "AB+", "AB+"
    AB_NEG = "AB-", "AB-"
    O_POS = "O+", "O+"
    O_NEG = "O-", "O-"
    UNKNOWN = "unknown", _("Unknown")


class AddressType(models.TextChoices):
    PERMANENT = "permanent", _("Permanent")
    TEMPORARY = "temporary", _("Temporary")
    CURRENT = "current", _("Current")


class GuardianRelation(models.TextChoices):
    FATHER = "father", _("Father")
    MOTHER = "mother", _("Mother")
    GUARDIAN = "guardian", _("Guardian")
    OTHER = "other", _("Other")


class DocumentType(models.TextChoices):
    PHOTO = "photo", _("Photo")
    CITIZENSHIP_FRONT = "citizenship_front", _("Citizenship Front")
    CITIZENSHIP_BACK = "citizenship_back", _("Citizenship Back")
    BIRTH_CERTIFICATE = "birth_certificate", _("Birth Certificate")
    PAN = "pan", _("PAN")
    PASSPORT = "passport", _("Passport")
    REGISTRATION = "registration", _("Registration")
    TRANSFER_CERTIFICATE = "transfer_certificate", _("Transfer Certificate")
    MARKSHEET = "marksheet", _("Marksheet")
    SIGNATURE = "signature", _("Signature")
    OTHER = "other", _("Other")


class Profile(models.Model):
    """
    One profile per user per school (multi-tenant friendly).
    Store personal info like DOB, blood group etc.

    NOTE:
    - Keep auth in accounts.User
    - Keep domain info here
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="profiles")
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="profile")

    date_of_birth_in_ad = models.DateField(null=True, blank=True)
    date_of_birth_in_bs = models.CharField(max_length=10, blank=True, default="")
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, default="")
    blood_group = models.CharField(max_length=10, choices=BloodGroup.choices, default=BloodGroup.UNKNOWN)

    nationality = models.CharField(max_length=60, blank=True, default="")
    religion = models.CharField(max_length=60, blank=True, default="")
    mother_tongue = models.CharField(max_length=60, blank=True, default="")

    # Nepal common IDs (optional)
    citizenship_no = models.CharField(max_length=80, blank=True, default="")
    pan_no = models.CharField(max_length=40, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "user"], name="uq_profile_school_user")
        ]

    def __str__(self):
        return f"Profile({self.user_id})"


class Address(models.Model):
    """
    Multiple addresses per profile (permanent/current/temporary).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="addresses")
    address_type = models.CharField(max_length=20, choices=AddressType.choices, db_index=True)

    country = models.CharField(max_length=80, blank=True, default="")
    province = models.CharField(max_length=80, blank=True, default="")
    district = models.CharField(max_length=80, blank=True, default="")
    municipality = models.CharField(max_length=80, blank=True, default="")
    ward_no = models.CharField(max_length=20, blank=True, default="")
    street = models.CharField(max_length=120, blank=True, default="")
    tole = models.CharField(max_length=120, blank=True, default="")
    house_no = models.CharField(max_length=40, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")

    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profile", "address_type"], name="uq_profile_address_type")
        ]

    def __str__(self):
        return f"{self.profile_id} - {self.address_type}"


class Guardian(models.Model):
    """
    Guardian/Parent info for a profile (mainly students, but can be reused).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="guardians")
    relation = models.CharField(max_length=20, choices=GuardianRelation.choices, db_index=True)

    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    occupation = models.CharField(max_length=120, blank=True, default="")

    is_primary = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["profile", "relation"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.relation})"


class ProfileDocument(models.Model):
    """
    Documents for a profile. Uses UploadedFile model.
    Supports multiple per type (e.g., multiple marksheets).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="documents")

    document_type = models.CharField(max_length=40, choices=DocumentType.choices, db_index=True)

    file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
    )

    issued_by = models.CharField(max_length=120, blank=True, default="")
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    remarks = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["profile", "document_type"]),
        ]

    def __str__(self):
        return f"{self.profile_id} - {self.document_type}"


class StudentOtherInfo(models.Model):
    is_disabled = models.BooleanField(default=False)
    disability_details = models.CharField(max_length=255, blank=True, default="")
    visual_issues = models.BooleanField(default=False)
    hearing_issues = models.BooleanField(default=False)
    mobility_issues = models.BooleanField(default=False)
    chronic_illness = models.BooleanField(default=False)
    chronic_illness_details = models.CharField(max_length=255, blank=True, default="")
    allergies = models.BooleanField(default=False)
    allergy_details = models.CharField(max_length=255, blank=True, default="")
    medications = models.BooleanField(default=False)
    medication_details = models.CharField(max_length=255, blank=True, default="")
    dietary_restrictions = models.BooleanField(default=False)
    dietary_restriction_details = models.CharField(max_length=255, blank=True, default="")
    other_health_issues = models.BooleanField(default=False)
    other_health_issue_details = models.CharField(max_length=255, blank=True, default="")
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="student_other_info")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profile"], name="uq_student_other_info_profile")
        ]

    def __str__(self):
        return f"StudentOtherInfo({self.profile_id})"


class TeacherLevelStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    DELETED = "deleted", "Deleted"

class TeacherLevel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.CharField(max_length=80)

    status = models.CharField(
        max_length=20,
        choices=TeacherLevelStatus.choices,
        default=TeacherLevelStatus.ACTIVE,
        db_index=True,
    )

    from django.db.models import Q

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["level"],
                condition=~Q(status=TeacherLevelStatus.DELETED),
                name="uq_teacher_level_level_not_deleted",
            )
        ]

    def __str__(self):
        return self.level

class TeacherSpecialization(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="teacher_specializations")
    subjects = models.ManyToManyField(
        "subjects.Subject",
        related_name="teacher_specializations",
    )
    teacher_level = models.ForeignKey(
        TeacherLevel,
        on_delete=models.SET_NULL,
        related_name="teacher_specializations",
        null=True,
        blank=True,
    )
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uq_teacher_specialization_user")
        ]
    def __str__(self):
        return f"TeacherSpecialization({self.user_id})"
