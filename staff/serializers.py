from django.db import transaction
from rest_framework import serializers
from accounts.models import User
from staff.models import StaffProfile, TeacherProfile, TeacherAssignment
from academics.models import AcademicYear, AcademicClass, Section


class StaffProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            "id", "user", "user_email", "user_phone", "first_name", "last_name",
            "school_id", "campus_id",
            "staff_type", "employee_code", "employment_status", "joined_date",
            "citizenship_no", "pan_no", "ssf_no",
            "permanent_address", "temporary_address",
            "citizenship_file", "contract_file",
            "created_at",
        ]
        read_only_fields = ["id", "school_id", "created_at"]


class StaffCreateSerializer(serializers.Serializer):
    """
    Create staff profile for an existing user (or create user if missing).
    """
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")

    campus_id = serializers.CharField(required=False, allow_blank=True, default="")
    staff_type = serializers.CharField()
    employee_code = serializers.CharField(required=False, allow_blank=True, default="")
    joined_date = serializers.DateField(required=False, allow_null=True)

    def create(self, validated_data):
        request = self.context["request"]
        school_id = request.school_id
        email = validated_data["email"].strip().lower()

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email,
                    password=None,  # set later
                    phone=validated_data.get("phone", ""),
                    first_name=validated_data.get("first_name", ""),
                    last_name=validated_data.get("last_name", ""),
                )

            # prevent duplicates
            existing = StaffProfile.objects.filter(user=user).first()
            if existing:
                return existing

            staff = StaffProfile.objects.create(
                user=user,
                school_id=school_id,
                campus_id=validated_data.get("campus_id", ""),
                staff_type=validated_data["staff_type"],
                employee_code=validated_data.get("employee_code", ""),
                joined_date=validated_data.get("joined_date"),
            )
        return staff


class TeacherProfileSerializer(serializers.ModelSerializer):
    staff_email = serializers.EmailField(source="staff.user.email", read_only=True)

    class Meta:
        model = TeacherProfile
        fields = [
            "id", "staff", "staff_email",
            "designation", "qualification", "signature_file",
        ]
        read_only_fields = ["id"]


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    teacher_email = serializers.EmailField(source="teacher.staff.user.email", read_only=True)
    year_name = serializers.CharField(source="academic_year.name", read_only=True)
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = TeacherAssignment
        fields = [
            "id",
            "teacher", "teacher_email",
            "academic_year", "year_name",
            "academic_class", "class_name",
            "section", "section_name",
            "subject_id",
            "is_class_teacher",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        year = attrs.get("academic_year")
        cls = attrs.get("academic_class")
        sec = attrs.get("section")

        if year.school_id != school_id:
            raise serializers.ValidationError({"academic_year": "Academic year not in this school."})
        if cls.school_id != school_id:
            raise serializers.ValidationError({"academic_class": "Class not in this school."})
        if cls.academic_year_id != year.id:
            raise serializers.ValidationError({"academic_class": "Class does not belong to academic year."})
        if sec and sec.academic_class_id != cls.id:
            raise serializers.ValidationError({"section": "Section does not belong to class."})

        return attrs
