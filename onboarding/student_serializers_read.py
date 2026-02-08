from rest_framework import serializers
from accounts.models import User
from profiles.models import Profile, Address, Guardian, ProfileDocument, StudentOtherInfo


class AddressReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"


class GuardianReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = "__all__"


class ProfileDocumentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileDocument
        fields = ["id", "document_type", "file", "issued_by", "issued_date", "expiry_date", "remarks", "created_at"]


class StudentOtherInfoReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentOtherInfo
        fields = "__all__"


class ProfileReadSerializer(serializers.ModelSerializer):
    addresses = AddressReadSerializer(many=True, read_only=True)
    guardians = GuardianReadSerializer(many=True, read_only=True)  # ✅ add
    documents = ProfileDocumentReadSerializer(many=True, read_only=True)
    student_other_info = StudentOtherInfoReadSerializer(many=True, read_only=True)

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
            "addresses",
            "guardians",          # ✅ add
            "documents",
            "student_other_info",
        ]


class StudentUserReadSerializer(serializers.ModelSerializer):
    profile = ProfileReadSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "email",
            "username",
            "role",
            "status",
            "profile",
        ]
