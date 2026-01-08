from rest_framework import serializers
from organization.models import School, Campus, SchoolSetting

class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = [
            "id", "code", "name", "address", "phone", "email",
            "timezone", "currency", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ["id", "school", "name", "address", "phone", "is_active"]
        read_only_fields = ["id"]

class SchoolSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolSetting
        fields = [
            "id", "school",
            "invoice_prefix", "receipt_prefix", "fiscal_year_label",
            "late_fee_fixed", "late_fee_percent", "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]
