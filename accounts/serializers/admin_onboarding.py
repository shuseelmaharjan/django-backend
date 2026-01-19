# accounts/serializers/admin_onboarding.py
from rest_framework import serializers
from accounts.models import User
from schools.models import School
from profiles.models import Profile, Address, ProfileDocument

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
            "user_photo", "citizenship_front", "citizenship_back",
            "is_active",
        ]


class AdminSchoolInfoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = [
            "code", "name",
            "address", "phone", "email",
            "logo_file",
            "pan_number", "registration_number",
            "pan_document_file", "registration_document_file",
            "user_photo", "citizenship_front", "citizenship_back",
            "is_active",
        ]


# -----------------------------
# Nested Address + Document inputs
# -----------------------------
class AddressInputSerializer(serializers.Serializer):
    address_type = serializers.ChoiceField(choices=Address._meta.get_field("address_type").choices)
    country = serializers.CharField(required=False, allow_blank=True)
    province = serializers.CharField(required=False, allow_blank=True)
    district = serializers.CharField(required=False, allow_blank=True)
    municipality = serializers.CharField(required=False, allow_blank=True)
    ward_no = serializers.CharField(required=False, allow_blank=True)
    street = serializers.CharField(required=False, allow_blank=True)
    tole = serializers.CharField(required=False, allow_blank=True)
    house_no = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    is_primary = serializers.BooleanField(required=False, default=False)


class DocumentInputSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=ProfileDocument._meta.get_field("document_type").choices)
    file = serializers.UUIDField()  # UploadedFile UUID
    issued_by = serializers.CharField(required=False, allow_blank=True)
    issued_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True)


class AdminClientInfoCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    school_id = serializers.UUIDField()

    # DOB: accept either AD or BS format; store AD
    date_of_birth = serializers.CharField(required=False, allow_blank=True)
    date_of_birth_type = serializers.ChoiceField(
        choices=[("ad", "AD"), ("bs", "BS")],
        required=False,
        default="ad",
    )

    gender = serializers.CharField(required=False, allow_blank=True)
    blood_group = serializers.CharField(required=False, allow_blank=True)
    nationality = serializers.CharField(required=False, allow_blank=True)
    religion = serializers.CharField(required=False, allow_blank=True)
    mother_tongue = serializers.CharField(required=False, allow_blank=True)
    citizenship_no = serializers.CharField(required=False, allow_blank=True)
    pan_no = serializers.CharField(required=False, allow_blank=True)
    extra = serializers.JSONField(required=False)

    # multiple addresses
    addresses = AddressInputSerializer(many=True, allow_empty=False)

    # typed documents
    documents = DocumentInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        dob_raw = (attrs.get("date_of_birth") or "").strip()
        dob_type = attrs.get("date_of_birth_type", "ad")

        if dob_raw:
            try:
                if dob_type == "ad":
                    datetime.datetime.strptime(dob_raw, "%Y-%m-%d")
                else:
                    _ = bs_to_ad_date(dob_raw)  # validate BS date by converting
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
            "date_of_birth",           # stored AD
            "date_of_birth_type",      # tells stored type
            "date_of_birth_display",   # bs/ad based on context
            "gender", "blood_group",
            "nationality", "religion", "mother_tongue",
            "citizenship_no", "pan_no", "extra",
            "addresses", "documents",
            "created_at", "updated_at",
        ]

    def get_date_of_birth_type(self, obj: Profile):
        return "ad"  # stored as AD always

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
    class Meta:
        model = School
        fields = [
            "id", "code", "name", "owner",
            "address", "phone", "email",
            "logo_file",
            "pan_number", "registration_number",
            "pan_document_file", "registration_document_file",
            "user_photo", "citizenship_front", "citizenship_back",
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
