from rest_framework import serializers
from schools.models import School   # model still lives in schools app
from filehandler.serializers import UploadedFileSerializer


class PublicSchoolSerializer(serializers.ModelSerializer):
    logo_file = UploadedFileSerializer(read_only=True)

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
            "pan_number",
            "registration_number",
        ]