# accounts/serializers/admin_onboarding.py
from rest_framework import serializers
from accounts.models import User
from schools.models import School
from profiles.models import Profile, Address, ProfileDocument, Gender, BloodGroup
from filehandler.serializers import UploadedFileSerializer
import datetime
import nepali_datetime


# -----------------------------
# Helpers for BS <-> AD DOB
# -----------------------------
def bs_to_ad_date(bs_date_str: str) -> datetime.date:
    y, m, d = map(int, bs_date_str.split("-"))
    bs = nepali_datetime.date(y, m, d)
    return bs.to_datetime_date()


def ad_to_bs_str(ad_date: datetime.date) -> str:
    bs = nepali_datetime.date.from_datetime_date(ad_date)
    return f"{bs.year:04d}-{bs.month:02d}-{bs.day:02d}"


# -----------------------------
# Nepal phone/tel validation (School.phone)
# -----------------------------
PHONE_STARTSWITH = ("97", "98")
TEL_STARTSWITH = ("01",)
PHONE_LENGTH = 10         # total digits (no dial code)
TEL_REST_LENGTH = 7       # digits AFTER '01' must be 7 => total 9


def normalize_digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def validate_nepal_phone_or_tel(value: str) -> str:
    """
    Accepts:
      - mobile: 97/98 + total 10 digits
      - tel: 01 + (7 digits after 01) => total 9 digits
    Supports optional 977 or +977 prefix (removed automatically).
    """
    raw = (value or "").strip()
    digits = normalize_digits(raw)

    # strip country code if present
    if digits.startswith("977") and len(digits) > 3:
        digits = digits[3:]

    if len(digits) == PHONE_LENGTH and digits.startswith(PHONE_STARTSWITH):
        return digits

    if digits.startswith(TEL_STARTSWITH):
        rest = digits[2:]
        if len(rest) == TEL_REST_LENGTH:
            return digits

    raise serializers.ValidationError(
        "Invalid phone. Use Nepal mobile (97/98 + 10 digits) or tel (01 + 7 digits after 01). "
        "Do not include dial code; +977/977 is allowed but will be stripped."
    )


# -----------------------------
# Personal Info
# -----------------------------
class AdminPersonalInfoCreateSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    middle_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        value = (value or "").strip()
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value


class AdminPersonalInfoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["phone", "email", "first_name", "middle_name", "last_name"]

    def validate_email(self, value):
        value = (value or "").strip()
        qs = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
        if value and qs.exists():
            raise serializers.ValidationError("Email already exists.")
        return value


# -----------------------------
# School Info (ALL mandatory)
# -----------------------------
class AdminSchoolInfoCreateSerializer(serializers.ModelSerializer):
    owner_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = School
        fields = [
            "owner_id",
            "code", "name",
            "address", "phone", "email",
            "logo_file",
            "pan_number", "registration_number",
            "pan_document_file", "registration_document_file",
            "is_active",
        ]
        extra_kwargs = {
            "code": {"required": True, "allow_blank": False},
            "name": {"required": True, "allow_blank": False},
            "address": {"required": True, "allow_blank": False},
            "phone": {"required": True, "allow_blank": False},
            "email": {"required": True, "allow_blank": False},
            "logo_file": {"required": True, "allow_null": False},
            "pan_number": {"required": True, "allow_blank": False},
            "registration_number": {"required": True, "allow_blank": False},
            "pan_document_file": {"required": True, "allow_null": False},
            "registration_document_file": {"required": True, "allow_null": False},
            "is_active": {"required": True},
        }

    def validate_phone(self, value):
        return validate_nepal_phone_or_tel(value)


class AdminSchoolInfoUpdateSerializer(serializers.ModelSerializer):
    """
    If you want UPDATE also mandatory, keep same rules.
    If you want partial update later, change required=False per field.
    """
    logo_file_url = serializers.SerializerMethodField(read_only=True)
    pan_document_file_url = serializers.SerializerMethodField(read_only=True)
    registration_document_file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = School
        fields = [
            "code", "name",
            "address", "phone", "email",
            "logo_file", "logo_file_url",
            "pan_number", "registration_number",
            "pan_document_file", "pan_document_file_url",
            "registration_document_file", "registration_document_file_url",
            "is_active",
        ]
        extra_kwargs = {
            "code": {"required": True, "allow_blank": False},
            "name": {"required": True, "allow_blank": False},
            "address": {"required": True, "allow_blank": False},
            "phone": {"required": True, "allow_blank": False},
            "email": {"required": True, "allow_blank": False},
            "logo_file": {"required": True, "allow_null": False},
            "pan_number": {"required": True, "allow_blank": False},
            "registration_number": {"required": True, "allow_blank": False},
            "pan_document_file": {"required": True, "allow_null": False},
            "registration_document_file": {"required": True, "allow_null": False},
            "is_active": {"required": True},
        }

    def get_logo_file_url(self, obj):
        if not obj.logo_file or not obj.logo_file.file:
            return None
        request = self.context.get("request")
        url = obj.logo_file.file.url
        return request.build_absolute_uri(url) if request else url

    def get_pan_document_file_url(self, obj):
        if not obj.pan_document_file or not obj.pan_document_file.file:
            return None
        request = self.context.get("request")
        url = obj.pan_document_file.file.url
        return request.build_absolute_uri(url) if request else url

    def get_registration_document_file_url(self, obj):
        if not obj.registration_document_file or not obj.registration_document_file.file:
            return None
        request = self.context.get("request")
        url = obj.registration_document_file.file.url
        return request.build_absolute_uri(url) if request else url

    def validate_phone(self, value):
        return validate_nepal_phone_or_tel(value)


# -----------------------------
# Nested Address + Document inputs
# -----------------------------
class AddressInputSerializer(serializers.Serializer):
    address_type = serializers.ChoiceField(choices=Address._meta.get_field("address_type").choices)

    country = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    province = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    district = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    municipality = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    ward_no = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    # ONLY THESE CAN BE NULL
    street = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tole = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    house_no = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    postal_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    is_primary = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        # Convert allowed-nulls into "" to fit model (model uses blank=True, default="")
        for k in ("street", "tole", "house_no", "postal_code"):
            if attrs.get(k) is None:
                attrs[k] = ""
        return attrs


class DocumentInputSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=ProfileDocument._meta.get_field("document_type").choices)
    file = serializers.UUIDField(allow_null=False, required=True)  # UploadedFile UUID

    issued_by = serializers.CharField(required=False, allow_blank=True, allow_null=False)

    # ONLY THESE CAN BE NULL
    issued_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)

    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=False)


# -----------------------------
# Client/Profile create (ALL mandatory except allowed null fields above)
# -----------------------------
class AdminClientInfoCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=True)
    school_id = serializers.UUIDField(required=True)

    date_of_birth = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    date_of_birth_type = serializers.ChoiceField(
        choices=[("ad", "AD"), ("bs", "BS")],
        required=True,
        allow_null=False,
    )

    gender = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    blood_group = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    nationality = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    religion = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    mother_tongue = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    citizenship_no = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    pan_no = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    addresses = AddressInputSerializer(many=True, allow_empty=False)
    documents = DocumentInputSerializer(many=True, allow_empty=False)

    def validate_gender(self, value: str):
        v = (value or "").strip().lower()
        mapping = {
            "male": Gender.MALE,
            "female": Gender.FEMALE,
            "other": Gender.OTHER,
        }
        if v not in mapping:
            raise serializers.ValidationError("Invalid gender. Use Male/Female/Other.")
        return mapping[v]

    def validate_blood_group(self, value: str):
        v = (value or "").strip()
        allowed = {c[0] for c in BloodGroup.choices}
        if v not in allowed:
            raise serializers.ValidationError(f"Invalid blood_group. Allowed: {sorted(allowed)}")
        return v

    def validate(self, attrs):
        # ---- null detection (only allowed nulls already handled in nested serializers)
        null_fields = []

        # top-level fields cannot be null
        for k in (
            "user_id", "school_id",
            "date_of_birth", "date_of_birth_type",
            "gender", "blood_group",
            "nationality", "religion", "mother_tongue",
            "citizenship_no", "pan_no",
            "addresses", "documents",
        ):
            if k in attrs and attrs[k] is None:
                null_fields.append(k)

        if null_fields:
            raise serializers.ValidationError({k: "This field cannot be null." for k in null_fields})

        # ---- DOB format check
        dob_raw = (attrs.get("date_of_birth") or "").strip()
        dob_type = attrs.get("date_of_birth_type", "ad")

        try:
            if dob_type == "ad":
                datetime.datetime.strptime(dob_raw, "%Y-%m-%d")
            else:
                _ = bs_to_ad_date(dob_raw)
        except Exception:
            raise serializers.ValidationError(
                {"date_of_birth": "Invalid date format. Use YYYY-MM-DD. If bs, ensure valid Nepali date."}
            )

        # only 1 primary
        primaries = [a for a in attrs["addresses"] if a.get("is_primary")]
        if len(primaries) > 1:
            raise serializers.ValidationError({"addresses": "Only one address can be primary."})

        return attrs


# -----------------------------
# Read serializers
# -----------------------------
class ProfileDocumentReadSerializer(serializers.ModelSerializer):
    file = UploadedFileSerializer(read_only=True)
    class Meta:
        model = ProfileDocument
        fields = ["id", "document_type", "file", "issued_by", "issued_date", "expiry_date", "remarks", "created_at"]


class AddressReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id", "address_type", "country", "province", "district", "municipality",
            "ward_no", "street", "tole", "house_no", "postal_code", "is_primary"
        ]


class ProfileReadSerializer(serializers.ModelSerializer):
    addresses = AddressReadSerializer(many=True, read_only=True)
    documents = ProfileDocumentReadSerializer(many=True, read_only=True)

    date_of_birth_type = serializers.SerializerMethodField()
    date_of_birth_display = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id", "school", "user",
            "date_of_birth",
            "date_of_birth_type",
            "date_of_birth_display",
            "gender", "blood_group",
            "nationality", "religion", "mother_tongue",
            "citizenship_no", "pan_no",
            "addresses", "documents",
            "created_at", "updated_at",
        ]

    def get_date_of_birth_type(self, obj: Profile):
        return "ad"

    def get_date_of_birth_display(self, obj: Profile):
        if not obj.date_of_birth:
            return None

        mode = (self.context.get("dob_display") or "bs").lower()
        if mode == "ad":
            return obj.date_of_birth.isoformat()

        try:
            return ad_to_bs_str(obj.date_of_birth)
        except Exception:
            return obj.date_of_birth.isoformat()


class SchoolReadSerializer(serializers.ModelSerializer):
    logo_file = UploadedFileSerializer(read_only=True)
    pan_document_file = UploadedFileSerializer(read_only=True)
    registration_document_file = UploadedFileSerializer(read_only=True)
    class Meta:
        model = School
        fields = [
            "id", "code", "name", "owner",
            "address", "phone", "email",
            "logo_file",
            "pan_number", "registration_number",
            "pan_document_file", "registration_document_file",
            "is_active", "created_at",
        ]


class AdminBundleReadSerializer(serializers.ModelSerializer):
    owned_schools = SchoolReadSerializer(many=True, read_only=True)
    profile = serializers.SerializerMethodField()
    profile_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "phone", "email",
            "first_name", "middle_name", "last_name",
            "role", "status", "username",
            "owned_schools",
            "profile",
            "profile_status",
        ]

    def get_profile(self, obj: User):
        school = obj.owned_schools.order_by("-created_at").first()
        if not school:
            return None
        prof = Profile.objects.filter(user=obj, school=school).first()
        return ProfileReadSerializer(prof, context=self.context).data if prof else None

    def get_profile_status(self, obj: User):
        school = obj.owned_schools.order_by("-created_at").first()
        if not school:
            return "incomplete"
        prof = Profile.objects.filter(user=obj, school=school).first()
        if not prof:
            return "incomplete"
        if prof.addresses.exists() and prof.documents.exists():
            return "complete"
        return "incomplete"
