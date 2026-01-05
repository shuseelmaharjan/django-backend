import uuid
from django.db import models
from common.constants import StudentStatus, GuardianType, AddressType, StudentDocumentType



class StudentProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="student_profile"
    )
    status = models.CharField(
        max_length=20,
        choices=StudentStatus.choices,
        default=StudentStatus.ENROLLED,
        db_index=True,
    )
    # Required org scope for Nepal school management
    school_id = models.CharField(max_length=64, db_index=True)

    # Optional: branch/campus (keep optional, not forced)
    campus_id = models.CharField(max_length=64, db_index=True, blank=True, default="")

    # Class/Section (optional at creation; can be assigned later after admission)
    class_id = models.CharField(max_length=64, db_index=True, blank=True, default="")
    section_id = models.CharField(max_length=64, db_index=True, blank=True, default="")

    # Common Nepal student fields (keep minimal)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True, default="")  # optional enum later
    blood_group = models.CharField(max_length=5, blank=True, default="")  # e.g. A+, O-

    # Optional: student photo
    profile_photo = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )

    # Optional: government IDs (Nepal context)
    birth_certificate_no = models.CharField(max_length=60, blank=True, default="")
    student_national_id = models.CharField(max_length=60, blank=True, default="")  # if applicable

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"StudentProfile({self.user.email})"

    def active_enrollment(self, academic_year_id=None):
        qs = self.enrollments.filter(is_active=True)
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        return qs.select_related("academic_year", "academic_class", "section").first()


class StudentAddress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="addresses"
    )
    address_type = models.CharField(
        max_length=20,
        choices=AddressType.choices,
        db_index=True
    )
    # Nepal administrative fields (flexible text)
    province = models.CharField(max_length=100, blank=True, default="")
    district = models.CharField(max_length=100, blank=True, default="")
    municipality = models.CharField(max_length=120, blank=True, default="")  # nagarpalika/gaupalika
    ward_no = models.CharField(max_length=10, blank=True, default="")
    tole = models.CharField(max_length=120, blank=True, default="")  # locality
    street = models.CharField(max_length=120, blank=True, default="")

    # Optional geo/post
    postal_code = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "address_type"],
                name="uq_student_address_type"
            )
        ]

    def __str__(self):
        return f"{self.student.user.email} - {self.address_type}"


class StudentGuardian(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="guardians"
    )

    guardian_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guardian_links"
    )
    # guardian_user optional: some schools don't create parent accounts immediately

    guardian_type = models.CharField(
        max_length=20,
        choices=GuardianType.choices,
        db_index=True
    )

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    occupation = models.CharField(max_length=120, blank=True, default="")

    citizenship_no = models.CharField(max_length=80, blank=True, default="")

    # Proof document (citizenship scan etc.) using your pattern
    citizenship_document = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )

    is_primary_contact = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["student", "guardian_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "guardian_type"],
                name="uq_student_guardian_type"
            )
        ]

    def __str__(self):
        return f"{self.student.user.email} - {self.guardian_type} ({self.full_name})"



class StudentDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="documents"
    )

    doc_type = models.CharField(
        max_length=30,
        choices=StudentDocumentType.choices,
        db_index=True
    )

    file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.CASCADE,
        related_name="+"
    )

    title = models.CharField(max_length=120, blank=True, default="")
    is_required = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.user.email} - {self.doc_type}"
