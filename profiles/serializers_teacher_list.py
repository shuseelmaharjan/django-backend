# profiles/serializers_teacher_list.py
from rest_framework import serializers
from accounts.models import User
from profiles.models import Profile, Address, Guardian, ProfileDocument, TeacherSpecialization
from filehandler.serializers import UploadedFileSerializer
from subjects.serializers import SubjectReadSerializer


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
        fields = [
            "id", "relation", "full_name", "phone", "email", "occupation", "is_primary"
        ]


class ProfileDocumentSerializer(serializers.ModelSerializer):
    file = UploadedFileSerializer(read_only=True)

    class Meta:
        model = ProfileDocument
        fields = [
            "id", "document_type", "file",
            "issued_by", "issued_date", "expiry_date",
            "remarks", "created_at",
        ]


class ProfileSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    guardians = GuardianSerializer(many=True, read_only=True)
    documents = ProfileDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "school",  # you can change to school_id if you want
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
        ]


class TeacherSpecializationSerializer(serializers.ModelSerializer):
    teacher_level_id = serializers.SerializerMethodField()
    teacher_level = serializers.SerializerMethodField()
    subject_ids = serializers.SerializerMethodField()
    subjects = SubjectReadSerializer(many=True, read_only=True)


    class Meta:
        model = TeacherSpecialization
        fields = [
            "teacher_level_id",
            "teacher_level",
            "subjects",
            "subject_ids",
        ]

    def get_teacher_level_id(self, obj):
        return obj.teacher_level_id

    def get_teacher_level(self, obj):
        return obj.teacher_level.level if obj.teacher_level else None

    def get_subject_ids(self, obj):
        # prefetched
        return [str(s.id) for s in obj.subjects.all()]


class TeacherFullSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile = ProfileSerializer(read_only=True)
    profile_id = serializers.SerializerMethodField()

    # Files
    profile_picture = UploadedFileSerializer(source="profile_picture_file", read_only=True)

    # Teacher specialization (unique per user)
    specialization = serializers.SerializerMethodField()


    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "email",
            "role",
            "status",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "profile_id",
            "profile",
            "profile_picture",
            "specialization",
        ]

    def get_full_name(self, obj: User) -> str:
        parts = [obj.first_name, getattr(obj, "middle_name", ""), obj.last_name]
        return " ".join([p for p in parts if p]).strip()

    def get_profile_id(self, obj: User):
        prof = getattr(obj, "profile", None)
        return getattr(prof, "id", None)

    def get_specialization(self, obj: User):
        # teacher_specializations is prefetched; unique constraint => take first
        specs = list(getattr(obj, "teacher_specializations", []).all())
        if not specs:
            return None
        return TeacherSpecializationSerializer(specs[0], context=self.context).data
