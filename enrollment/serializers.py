from django.db import transaction
from rest_framework import serializers
from enrollment.models import StudentEnrollment, PromotionLog
from academics.models import AcademicYear, AcademicClass, Section
from students.models import StudentProfile

class StudentEnrollmentSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    year_name = serializers.CharField(source="academic_year.name", read_only=True)
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = StudentEnrollment
        fields = [
            "id", "school_id",
            "student", "student_email",
            "academic_year", "year_name",
            "academic_class", "class_name",
            "section", "section_name",
            "roll_no", "symbol_no",
            "enrolled_on", "is_active",
        ]
        read_only_fields = ["id", "school_id", "enrolled_on"]

class EnrollRequestSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    academic_year_id = serializers.UUIDField()
    academic_class_id = serializers.UUIDField()
    section_id = serializers.UUIDField(required=False, allow_null=True)
    roll_no = serializers.CharField(required=False, allow_blank=True, default="")
    symbol_no = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        student = StudentProfile.objects.filter(id=attrs["student_id"], school_id=school_id).first()
        if not student:
            raise serializers.ValidationError({"student_id": "Invalid student for this school."})

        year = AcademicYear.objects.filter(id=attrs["academic_year_id"], school_id=school_id).first()
        if not year:
            raise serializers.ValidationError({"academic_year_id": "Invalid academic year for this school."})

        cls = AcademicClass.objects.filter(
            id=attrs["academic_class_id"], school_id=school_id, academic_year_id=year.id
        ).first()
        if not cls:
            raise serializers.ValidationError({"academic_class_id": "Invalid class for this year/school."})

        sec_id = attrs.get("section_id")
        if sec_id:
            sec = Section.objects.filter(id=sec_id, academic_class_id=cls.id).first()
            if not sec:
                raise serializers.ValidationError({"section_id": "Invalid section for this class."})

        attrs["_student"] = student
        attrs["_year"] = year
        attrs["_class"] = cls
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        school_id = request.school_id

        student = validated_data["_student"]
        year = validated_data["_year"]
        cls = validated_data["_class"]
        section_id = validated_data.get("section_id")

        with transaction.atomic():
            # only one active enrollment per student per year
            StudentEnrollment.objects.filter(student=student, academic_year=year).update(is_active=False)

            enr = StudentEnrollment.objects.create(
                school_id=school_id,
                student=student,
                academic_year=year,
                academic_class=cls,
                section_id=section_id,
                roll_no=validated_data.get("roll_no", ""),
                symbol_no=validated_data.get("symbol_no", ""),
                is_active=True,
            )

            # Optional: keep StudentProfile cache fields in sync (since you have them)
            student.class_id = str(cls.id)
            student.section_id = str(section_id or "")
            student.save(update_fields=["class_id", "section_id"])

        return enr

class PromoteRequestSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    from_enrollment_id = serializers.UUIDField()
    to_academic_year_id = serializers.UUIDField()
    to_academic_class_id = serializers.UUIDField()
    to_section_id = serializers.UUIDField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        enr = StudentEnrollment.objects.select_related("student").filter(
            id=attrs["from_enrollment_id"],
            school_id=school_id,
            student_id=attrs["student_id"],
            is_active=True,
        ).first()
        if not enr:
            raise serializers.ValidationError({"from_enrollment_id": "Active enrollment not found."})

        year = AcademicYear.objects.filter(id=attrs["to_academic_year_id"], school_id=school_id).first()
        if not year:
            raise serializers.ValidationError({"to_academic_year_id": "Invalid academic year."})

        cls = AcademicClass.objects.filter(
            id=attrs["to_academic_class_id"], school_id=school_id, academic_year_id=year.id
        ).first()
        if not cls:
            raise serializers.ValidationError({"to_academic_class_id": "Invalid class for target year."})

        sec_id = attrs.get("to_section_id")
        if sec_id:
            sec = Section.objects.filter(id=sec_id, academic_class_id=cls.id).first()
            if not sec:
                raise serializers.ValidationError({"to_section_id": "Invalid section for target class."})

        attrs["_from_enrollment"] = enr
        attrs["_to_year"] = year
        attrs["_to_class"] = cls
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        school_id = request.school_id

        from_enr = validated_data["_from_enrollment"]
        student = from_enr.student
        to_year = validated_data["_to_year"]
        to_cls = validated_data["_to_class"]
        to_section_id = validated_data.get("to_section_id")

        with transaction.atomic():
            # deactivate current
            from_enr.is_active = False
            from_enr.save(update_fields=["is_active"])

            # create new enrollment
            to_enr = StudentEnrollment.objects.create(
                school_id=school_id,
                student=student,
                academic_year=to_year,
                academic_class=to_cls,
                section_id=to_section_id,
                is_active=True,
            )

            PromotionLog.objects.create(
                school_id=school_id,
                student=student,
                from_enrollment=from_enr,
                to_enrollment=to_enr,
                promoted_by=request.user if request.user.is_authenticated else None,
                remarks=validated_data.get("remarks", ""),
            )

            # sync cache fields
            student.class_id = str(to_cls.id)
            student.section_id = str(to_section_id or "")
            student.save(update_fields=["class_id", "section_id"])

        return to_enr
