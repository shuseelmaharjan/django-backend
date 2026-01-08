from django.db import transaction
from rest_framework import serializers
from accounts.models import User
from students.models import StudentProfile, StudentGuardian, StudentAddress, StudentDocument

class StudentUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    password = serializers.CharField(required=False, allow_blank=True)  # optional; can create unusable

class StudentProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "school_id", "campus_id",
            "status",
            "class_id", "section_id",
            "date_of_birth", "gender", "blood_group",
            "birth_certificate_no", "student_national_id",
            "created_at",
            "user", "user_email", "user_phone", "first_name", "last_name",
        ]
        read_only_fields = ["id", "school_id", "created_at", "user"]

class StudentCreateSerializer(serializers.Serializer):
    user = StudentUserCreateSerializer()
    campus_id = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.CharField(required=False, default="enrolled")
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True, default="")
    blood_group = serializers.CharField(required=False, allow_blank=True, default="")
    birth_certificate_no = serializers.CharField(required=False, allow_blank=True, default="")
    student_national_id = serializers.CharField(required=False, allow_blank=True, default="")

    def create(self, validated_data):
        request = self.context["request"]
        school_id = request.school_id

        user_data = validated_data["user"]
        email = user_data["email"].lower().strip()

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email,
                    password=user_data.get("password") or None,
                    phone=user_data.get("phone", ""),
                    first_name=user_data.get("first_name", ""),
                    last_name=user_data.get("last_name", ""),
                )

            profile = StudentProfile.objects.create(
                user=user,
                school_id=school_id,
                campus_id=validated_data.get("campus_id", ""),
                status=validated_data.get("status", "enrolled"),
                date_of_birth=validated_data.get("date_of_birth"),
                gender=validated_data.get("gender", ""),
                blood_group=validated_data.get("blood_group", ""),
                birth_certificate_no=validated_data.get("birth_certificate_no", ""),
                student_national_id=validated_data.get("student_national_id", ""),
            )

        return profile

class StudentGuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentGuardian
        fields = [
            "id", "student", "guardian_user", "guardian_type",
            "full_name", "phone", "email", "occupation", "citizenship_no",
            "citizenship_document", "is_primary_contact",
        ]
        read_only_fields = ["id"]

class StudentAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAddress
        fields = [
            "id", "student", "address_type",
            "province", "district", "municipality", "ward_no", "tole", "street", "postal_code",
        ]
        read_only_fields = ["id"]

class StudentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDocument
        fields = ["id", "student", "doc_type", "file", "title", "is_required", "is_verified", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]
