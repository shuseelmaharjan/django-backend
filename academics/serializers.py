from rest_framework import serializers
from academics.models import AcademicYear, AcademicClass, Section

class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "school_id", "name", "start_date", "end_date", "is_active"]
        read_only_fields = ["id", "school_id"]

class AcademicClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicClass
        fields = ["id", "school_id", "academic_year", "code", "name", "order", "is_active"]
        read_only_fields = ["id", "school_id"]

class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ["id", "academic_class", "name", "capacity", "is_active"]
        read_only_fields = ["id"]
