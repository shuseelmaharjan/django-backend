# profiles/models.py
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


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
