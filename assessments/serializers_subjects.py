from rest_framework import serializers
from assessments.models import Subject


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "school_id", "code", "name", "is_active"]
        read_only_fields = ["id", "school_id"]
