from rest_framework import serializers
from schools.models import School   # model still lives in schools app
from filehandler.serializers import UploadedFileSerializer


class PublicSchoolSerializer(serializers.ModelSerializer):
    logo_file = serializers.SerializerMethodField()

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

    def get_logo_file(self, obj):
        if not obj.logo_file:
            return None
        return UploadedFileSerializer(
            obj.logo_file,
            context=self.context
        ).data