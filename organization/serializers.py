from rest_framework import serializers
from .models import School, Campus, SchoolSetting
from utils.phone_validator import clean_and_validate_phone


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = [
            'id', 'code', 'name', 'address', 'phone', 'email',
            'logo_file', 'timezone', 'currency', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_phone(self, value):
        """Validate phone number"""
        if value:
            return clean_and_validate_phone(value)
        return value

    def validate_is_active(self, value):
        """Warn if trying to set multiple schools to active"""
        if value:
            instance = self.instance
            active_schools = School.objects.filter(is_active=True)
            if instance:
                active_schools = active_schools.exclude(pk=instance. pk)
            if active_schools.exists():
                # The model's save method will handle deactivating others
                pass
        return value


class CampusSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = Campus
        fields = [
            'id', 'school', 'school_name', 'name', 'address',
            'phone', 'is_active'
        ]
        read_only_fields = ['id']

    def validate_phone(self, value):
        """Validate phone number"""
        if value:
            return clean_and_validate_phone(value)
        return value

    def validate(self, attrs):
        """Validate campus data"""
        school = attrs.get('school', getattr(self. instance, 'school', None))
        name = attrs.get('name', getattr(self.instance, 'name', None))
        is_active = attrs.get('is_active', getattr(self. instance, 'is_active', None))

        # Check unique together constraint
        if school and name:
            campus_query = Campus.objects.filter(school=school, name=name)
            if self.instance:
                campus_query = campus_query.exclude(pk=self. instance.pk)
            if campus_query.exists():
                raise serializers.ValidationError(
                    "A campus with this name already exists for this school."
                )

        return attrs


class SchoolSettingSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = SchoolSetting
        fields = [
            'id', 'school', 'school_name', 'invoice_prefix', 'receipt_prefix',
            'fiscal_year_label', 'late_fee_fixed', 'late_fee_percent',
            'is_active', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']