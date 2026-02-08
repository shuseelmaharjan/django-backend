from rest_framework import serializers
from accounts.models import User
from profiles.models import Profile, Address, ProfileDocument


class AddressReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"


class ProfileDocumentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileDocument
        fields = ["id", "document_type", "file", "issued_by", "issued_date", "expiry_date", "remarks", "created_at"]


class ProfileReadSerializer(serializers.ModelSerializer):
    addresses = AddressReadSerializer(many=True, read_only=True)
    documents = ProfileDocumentReadSerializer(many=True, read_only=True)

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
            "documents",
        ]


class StaffUserReadSerializer(serializers.ModelSerializer):
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
