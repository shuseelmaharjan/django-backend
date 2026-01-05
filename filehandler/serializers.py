# filehandler/serializers.py
from rest_framework import serializers
from filehandler.models import UploadedFile


class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = [
            "id",
            "file",
            "file_type",
            "original_name",
            "size_bytes",
            "is_temporary",
            "meta",
            "uploaded_at",
        ]
        read_only_fields = ["id", "original_name", "size_bytes", "uploaded_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        instance = UploadedFile(**validated_data)

        if request and request.user and request.user.is_authenticated:
            instance.uploaded_by = request.user

        instance.save()  # calls full_clean() inside model.save()
        return instance
