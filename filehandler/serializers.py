from rest_framework import serializers
from django.urls import reverse
from filehandler.models import UploadedFile

class UploadedFileSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=True)
    file_url = serializers.SerializerMethodField(read_only=True)

    # ✅ add this
    download_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UploadedFile
        fields = [
            "id",
            "file",         # upload input
            "file_url",     # output url
            "download_url",
            "file_type",
            "original_name",
            "size_bytes",
            "is_temporary",
            "meta",
            "uploaded_at",
        ]
        read_only_fields = [
            "id",
            "original_name",
            "size_bytes",
            "uploaded_at",
            "file_url",
            "download_url",
        ]

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_download_url(self, obj):
        request = self.context.get("request")
        path = reverse("file-handler:file-download", kwargs={"id": obj.id})
        return request.build_absolute_uri(path) if request else path
