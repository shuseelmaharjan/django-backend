from rest_framework import serializers
from filehandler.serializers import UploadedFileSerializer
from filehandler.models import UploadedFile
from .models import School, SchoolSetting
from utils.phone_validator import clean_and_validate_phone


class SchoolSerializer(serializers.ModelSerializer):
    logo_file = UploadedFileSerializer(read_only=True)
    logo_file_id = serializers.PrimaryKeyRelatedField(
        queryset=UploadedFile.objects.all(),
        source="logo_file",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = School
        fields = [
            "id",
            "code",
            "name",
            "address",
            "phone",
            "email",
            "logo_file",
            "logo_file_id",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_phone(self, value: str):
        if value:
            return clean_and_validate_phone(value)
        return value


class SchoolSettingSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = SchoolSetting
        fields = [
            "id",
            "school",
            "school_name",
            "invoice_prefix",
            "receipt_prefix",
            "fiscal_year_label",
            "late_fee_fixed",
            "late_fee_percent",
            "is_active",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def validate_school(self, school):
        request = self.context.get("request")
        if request and request.method == "POST":
            if SchoolSetting.objects.filter(school=school).exists():
                raise serializers.ValidationError(
                    "Settings already exist for this school. Use PUT/PATCH to update."
                )
        return school