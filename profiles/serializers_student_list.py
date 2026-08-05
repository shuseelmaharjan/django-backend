from rest_framework import serializers

from accounts.models import User
from profiles.models import Profile, Address, Guardian, ProfileDocument, StudentOtherInfo
from academics.models import StudentEnrollments
from filehandler.serializers import UploadedFileSerializer


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id", "address_type",
            "country", "province", "district", "municipality",
            "ward_no", "street", "tole", "house_no", "postal_code",
            "is_primary",
        ]


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = ["id", "relation", "full_name", "phone", "email", "occupation", "is_primary"]


class ProfileDocumentSerializer(serializers.ModelSerializer):
    file = UploadedFileSerializer(read_only=True)

    class Meta:
        model = ProfileDocument
        fields = [
            "id", "document_type", "file",
            "issued_by", "issued_date", "expiry_date",
            "remarks", "created_at",
        ]


class StudentOtherInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentOtherInfo
        fields = [
            "is_disabled", "disability_details",
            "visual_issues", "hearing_issues", "mobility_issues",
            "chronic_illness", "chronic_illness_details",
            "allergies", "allergy_details",
            "medications", "medication_details",
            "dietary_restrictions", "dietary_restriction_details",
            "other_health_issues", "other_health_issue_details",
        ]


class ProfileSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    guardians = GuardianSerializer(many=True, read_only=True)
    documents = ProfileDocumentSerializer(many=True, read_only=True)
    student_other_info = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "school",
            "date_of_birth_in_ad",
            "date_of_birth_in_bs",
            "gender",
            "blood_group",
            "nationality",
            "religion",
            "mother_tongue",
            "citizenship_no",
            "pan_no",
            "created_at",
            "updated_at",
            "addresses",
            "guardians",
            "documents",
            "student_other_info",
        ]

    def get_student_other_info(self, obj: Profile):
        # related_name="student_other_info" but it's FK; use first()
        info = obj.student_other_info.all().first()
        return StudentOtherInfoSerializer(info).data if info else None


class StudentEnrollmentMiniSerializer(
    serializers.ModelSerializer
):
    batch_id = serializers.IntegerField(
        read_only=True,
    )

    academic_class_id = serializers.UUIDField(
        read_only=True,
    )

    section_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )

    batch_name = serializers.CharField(
        source="batch.name",
        read_only=True,
    )

    class_name = serializers.CharField(
        source="academic_class.name",
        read_only=True,
    )

    section_name = serializers.CharField(
        source="section.name",
        read_only=True,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = StudentEnrollments
        fields = [
            "id",
            "batch_id",
            "batch_name",
            "academic_class_id",
            "class_name",
            "section_id",
            "section_name",
            "status",
            "enrolled_at",
        ]

class StudentFullSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_id = serializers.SerializerMethodField()
    profile = ProfileSerializer(read_only=True)

    # profile picture file (optional)
    profile_picture = UploadedFileSerializer(source="profile_picture_file", read_only=True)

    # latest/current enrollment info (optional but very useful)
    current_enrollment = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "email",
            "username",
            "role",
            "status",
            "registration_no",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "profile_id",
            "profile",
            "profile_picture",
            "current_enrollment",
        ]

    def get_full_name(self, obj: User) -> str:
        parts = [obj.first_name, getattr(obj, "middle_name", ""), obj.last_name]
        return " ".join([p for p in parts if p]).strip()

    def get_profile_id(self, obj: User):
        prof = getattr(obj, "profile", None)
        return getattr(prof, "id", None)

    def get_current_enrollment(self, obj: User):
        # prefetched as "enrollments" in the view; take most recent
        enrollments = list(getattr(obj, "enrollments", []).all())
        if not enrollments:
            return None
        return StudentEnrollmentMiniSerializer(enrollments[0], context=self.context).data
