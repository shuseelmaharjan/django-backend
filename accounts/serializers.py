# accounts/serializers.py
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from accounts.models import User, RoleAssignment, Role
from students.models import StudentProfile, StudentAddress, StudentGuardian, StudentDocument
from staff.models import StaffProfile, TeacherProfile, TeacherAssignment


class ChangePasswordRequestSerializer(serializers.Serializer):
    oldPassword = serializers.CharField(write_only=True)
    newPassword = serializers.CharField(write_only=True)
    confirmPassword = serializers.CharField(write_only=True)

    def validate(self, attrs):
        new_pw = attrs["newPassword"]
        confirm = attrs["confirmPassword"]
        if new_pw != confirm:
            raise serializers.ValidationError({"confirmPassword": "Passwords do not match."})

        # Run Django validators (min length, common password, etc.)
        user = self.context["request"].user
        validate_password(new_pw, user=user)

        return attrs


class ChangePasswordResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()

# -------------------------
# Roles
# -------------------------
class RoleAssignmentMiniSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = RoleAssignment
        fields = ["id", "role_code", "role_name", "scope_type", "scope_id"]


# -------------------------
# User (core)
# -------------------------
class UserProfileSerializer(serializers.ModelSerializer):
    """
    This defines what "user" looks like in /my-profile response.
    """
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "phone",
            "status",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        ]


# -------------------------
# Student nested pieces
# -------------------------
class StudentAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAddress
        fields = [
            "id",
            "address_type",
            "province",
            "district",
            "municipality",
            "ward_no",
            "tole",
            "street",
            "postal_code",
        ]


class StudentGuardianSerializer(serializers.ModelSerializer):
    guardian_user_id = serializers.SerializerMethodField()

    class Meta:
        model = StudentGuardian
        fields = [
            "id",
            "guardian_type",
            "full_name",
            "phone",
            "email",
            "occupation",
            "citizenship_no",
            "is_primary_contact",
            "guardian_user_id",
            "citizenship_document",
        ]

    def get_guardian_user_id(self, obj):
        return str(obj.guardian_user_id) if obj.guardian_user_id else None


class StudentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDocument
        fields = [
            "id",
            "doc_type",
            "title",
            "is_required",
            "is_verified",
            "uploaded_at",
            "file",
        ]


class StudentProfileSerializer(serializers.ModelSerializer):
    addresses = StudentAddressSerializer(many=True, read_only=True)
    guardians = StudentGuardianSerializer(many=True, read_only=True)
    documents = StudentDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "status",
            "school_id",
            "campus_id",
            "class_id",
            "section_id",
            "date_of_birth",
            "gender",
            "blood_group",
            "profile_photo",
            "birth_certificate_no",
            "student_national_id",
            "created_at",
            "addresses",
            "guardians",
            "documents",
        ]


# -------------------------
# Staff nested pieces
# -------------------------
class StaffProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffProfile
        fields = [
            "id",
            "school_id",
            "campus_id",
            "staff_type",
            "employee_code",
            "employment_status",
            "joined_date",
            "citizenship_no",
            "pan_no",
            "ssf_no",
            "permanent_address",
            "temporary_address",
            "citizenship_file",
            "contract_file",
            "created_at",
        ]


class TeacherAssignmentMiniSerializer(serializers.ModelSerializer):
    academic_year_id = serializers.CharField(source="academic_year.id", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)

    academic_class_id = serializers.CharField(source="academic_class.id", read_only=True)
    academic_class_name = serializers.CharField(source="academic_class.name", read_only=True)

    section_id = serializers.SerializerMethodField()
    section_name = serializers.SerializerMethodField()

    class Meta:
        model = TeacherAssignment
        fields = [
            "id",
            "academic_year_id",
            "academic_year_name",
            "academic_class_id",
            "academic_class_name",
            "section_id",
            "section_name",
            "subject_id",
            "is_class_teacher",
        ]

    def get_section_id(self, obj):
        return str(obj.section_id) if obj.section_id else None

    def get_section_name(self, obj):
        return obj.section.name if obj.section else None


class TeacherProfileSerializer(serializers.ModelSerializer):
    assignments = TeacherAssignmentMiniSerializer(many=True, read_only=True)

    class Meta:
        model = TeacherProfile
        fields = [
            "id",
            "designation",
            "qualification",
            "signature_file",
            "assignments",
        ]


# -------------------------
# Final response
# -------------------------
class MyProfileResponseSerializer(serializers.Serializer):
    user = UserProfileSerializer()
    roles = RoleAssignmentMiniSerializer(many=True)

    # optional blocks
    staff = StaffProfileSerializer(required=False)
    teacher = TeacherProfileSerializer(required=False)
    student = StudentProfileSerializer(required=False)

# -------------------------
# ROLE CRUD
# -------------------------
class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "school_id", "code", "name", "is_system"]

    def validate_code(self, value: str):
        return value.strip().lower()


# -------------------------
# ROLE ASSIGNMENT CRUD
# -------------------------
class RoleAssignmentSerializer(serializers.ModelSerializer):
    """
    Create role assignments to users with scope.
    """
    user_id = serializers.UUIDField(write_only=True)
    role_id = serializers.UUIDField(write_only=True)

    user_email = serializers.EmailField(source="user.email", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "user_id",
            "role_id",
            "user_email",
            "role_code",
            "role_name",
            "scope_type",
            "scope_id",
            "valid_from",
            "valid_to",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "user_email", "role_code", "role_name"]

    def validate(self, attrs):
        # Resolve references
        user_id = attrs.get("user_id")
        role_id = attrs.get("role_id")

        user = User.objects.filter(id=user_id).first()
        if not user:
            raise serializers.ValidationError({"user_id": "User not found."})

        role = Role.objects.filter(id=role_id).first()
        if not role:
            raise serializers.ValidationError({"role_id": "Role not found."})

        # Save resolved objects for create()
        attrs["_user_obj"] = user
        attrs["_role_obj"] = role

        # Basic sanity: scope_id required if scope_type not global
        scope_type = attrs.get("scope_type")
        scope_id = (attrs.get("scope_id") or "").strip()

        if scope_type != "global" and scope_id in ["", "*"]:
            raise serializers.ValidationError({"scope_id": "scope_id is required for non-global scopes."})

        return attrs

    def create(self, validated_data):
        user = validated_data.pop("_user_obj")
        role = validated_data.pop("_role_obj")

        validated_data.pop("user_id", None)
        validated_data.pop("role_id", None)

        return RoleAssignment.objects.create(user=user, role=role, **validated_data)

    def update(self, instance, validated_data):
        # disallow switching user/role in update for safety
        validated_data.pop("user_id", None)
        validated_data.pop("role_id", None)
        validated_data.pop("_user_obj", None)
        validated_data.pop("_role_obj", None)

        return super().update(instance, validated_data)