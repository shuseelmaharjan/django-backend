from django.db import transaction
from rest_framework import serializers

from accounts.models import User
from filehandler.constants import FileType
from filehandler.models import UploadedFile
from filehandler.serializers import UploadedFileSerializer

from profiles.models import (
    Profile,
    Address,
    AddressType,
    Guardian,
    DocumentType,
    ProfileDocument,
    StudentOtherInfo,
)


class ManagementUserSummarySerializer(serializers.ModelSerializer):
    profile_picture_file = UploadedFileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "email",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "role",
            "status",
            "profile_picture_file",
            "username",
            "registration_no",
            "date_joined",
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return " ".join(
            filter(
                None,
                [
                    obj.first_name,
                    obj.middle_name,
                    obj.last_name,
                ],
            )
        ).strip()


class ManagementUserIdentityUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "first_name",
            "middle_name",
            "last_name",
        ]
        extra_kwargs = {
            "first_name": {
                "required": False,
                "allow_blank": True,
                "max_length": 150,
            },
            "middle_name": {
                "required": False,
                "allow_blank": True,
                "max_length": 80,
            },
            "last_name": {
                "required": False,
                "allow_blank": True,
                "max_length": 150,
            },
        }

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one name field must be provided."
            )
        return attrs


class ManagementProfilePictureUpdateSerializer(serializers.Serializer):
    profile_picture_file = serializers.PrimaryKeyRelatedField(
        queryset=UploadedFile.objects.all(),
        allow_null=True,
        required=True,
    )

    def validate_profile_picture_file(self, file_obj):
        if file_obj is None:
            return file_obj

        request = self.context["request"]

        if file_obj.file_type != FileType.IMAGE:
            raise serializers.ValidationError(
                "The selected file must be an image."
            )

        if not file_obj.file:
            raise serializers.ValidationError(
                "The selected file is unavailable."
            )

        # Staff can use files uploaded by themselves, the target user,
        # or unassigned files.
        target_user = self.context["target_user"]

        allowed_owner_ids = {
            request.user.id,
            target_user.id,
            None,
        }

        if file_obj.uploaded_by_id not in allowed_owner_ids:
            if not request.user.is_superuser:
                raise serializers.ValidationError(
                    "This file belongs to another user."
                )

        return file_obj

    @transaction.atomic
    def update(self, instance, validated_data):
        file_obj = validated_data["profile_picture_file"]

        instance.profile_picture_file = file_obj
        instance.save(update_fields=["profile_picture_file"])

        if file_obj:
            update_fields = []

            if file_obj.is_temporary:
                file_obj.is_temporary = False
                update_fields.append("is_temporary")

            if file_obj.uploaded_by_id is None:
                file_obj.uploaded_by = instance
                update_fields.append("uploaded_by")

            if update_fields:
                file_obj.save(update_fields=update_fields)

        return instance


class PersonalInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "id",
            "date_of_birth_in_ad",
            "date_of_birth_in_bs",
            "gender",
            "blood_group",
            "nationality",
            "religion",
            "mother_tongue",
            "citizenship_no",
            "pan_no",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class PersonalInfoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "date_of_birth_in_ad",
            "date_of_birth_in_bs",
            "gender",
            "blood_group",
            "nationality",
            "religion",
            "mother_tongue",
            "citizenship_no",
            "pan_no",
        ]
        extra_kwargs = {
            field: {"required": False}
            for field in fields
        }

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one personal information field must be provided."
            )
        return attrs


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "address_type",
            "country",
            "province",
            "district",
            "municipality",
            "ward_no",
            "street",
            "tole",
            "house_no",
            "postal_code",
            "is_primary",
        ]
        read_only_fields = [
            "id",
            "address_type",
        ]


class AddressUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "country",
            "province",
            "district",
            "municipality",
            "ward_no",
            "street",
            "tole",
            "house_no",
            "postal_code",
            "is_primary",
        ]
        extra_kwargs = {
            field: {"required": False}
            for field in fields
        }

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one address field must be provided."
            )
        return attrs


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = [
            "id",
            "relation",
            "full_name",
            "phone",
            "email",
            "occupation",
            "is_primary",
        ]
        read_only_fields = ["id"]


class GuardianCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = [
            "relation",
            "full_name",
            "phone",
            "email",
            "occupation",
            "is_primary",
        ]
        extra_kwargs = {
            "relation": {"required": False},
            "full_name": {"required": False},
            "phone": {"required": False},
            "email": {"required": False},
            "occupation": {"required": False},
            "is_primary": {"required": False},
        }

    def validate(self, attrs):
        if self.instance is None:
            if not attrs.get("relation"):
                raise serializers.ValidationError({
                    "relation": "Guardian relation is required."
                })

            if not attrs.get("full_name"):
                raise serializers.ValidationError({
                    "full_name": "Guardian full name is required."
                })

        if not attrs:
            raise serializers.ValidationError(
                "At least one guardian field must be provided."
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        profile = self.context["profile"]

        if validated_data.get("is_primary"):
            Guardian.objects.filter(
                profile=profile,
                is_primary=True,
            ).update(is_primary=False)

        return Guardian.objects.create(
            profile=profile,
            **validated_data,
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        if validated_data.get("is_primary"):
            Guardian.objects.filter(
                profile=instance.profile,
                is_primary=True,
            ).exclude(pk=instance.pk).update(is_primary=False)

        return super().update(instance, validated_data)


class ProfileDocumentSerializer(serializers.ModelSerializer):
    file = UploadedFileSerializer(read_only=True)

    class Meta:
        model = ProfileDocument
        fields = [
            "id",
            "document_type",
            "file",
            "issued_by",
            "issued_date",
            "expiry_date",
            "remarks",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]


class NullableDateField(serializers.DateField):
    """
    Accepts an empty string from frontend forms and converts it to None.

    DRF's standard DateField rejects:
        ""

    even when allow_null=True.
    """

    def to_internal_value(self, value):
        if value in ("", None):
            return None

        return super().to_internal_value(value)


class ProfileDocumentCreateUpdateSerializer(
    serializers.ModelSerializer
):
    file = serializers.PrimaryKeyRelatedField(
        queryset=UploadedFile.objects.all(),
        required=False,
    )

    issued_date = NullableDateField(
        required=False,
        allow_null=True,
    )

    expiry_date = NullableDateField(
        required=False,
        allow_null=True,
    )

    # All values currently supported by the model choices.
    ALLOWED_DOCUMENT_TYPES = {
        "photo",
        "citizenship_front",
        "citizenship_back",
        "birth_certificate",
        "pan",
        "passport",
        "registration",
        "transfer_certificate",
        "marksheet",
        "signature",
        "other",
    }

    # Student users may only have these document types.
    STUDENT_ALLOWED_DOCUMENT_TYPES = {
        "photo",
        "birth_certificate",
        "transfer_certificate",
        "marksheet",
    }

    # Required when completing/finalizing a student profile.
    # Do not enforce this set during an individual document upload.
    STUDENT_REQUIRED_DOCUMENT_TYPES = {
        "photo",
        "birth_certificate",
    }

    STUDENT_OPTIONAL_DOCUMENT_TYPES = {
        "transfer_certificate",
        "marksheet",
    }

    # These document types may store issue metadata.
    DOCUMENT_TYPES_WITH_DETAILS = {
        "birth_certificate",
        "pan",
        "passport",
        "registration",
        "transfer_certificate",
        "marksheet",
        "other",
    }

    # Only passports may store an expiry date.
    DOCUMENT_TYPES_WITH_EXPIRY = {
        "passport",
    }

    class Meta:
        model = ProfileDocument
        fields = [
            "document_type",
            "file",
            "issued_by",
            "issued_date",
            "expiry_date",
            "remarks",
        ]
        extra_kwargs = {
            "document_type": {
                "required": False,
            },
            "issued_by": {
                "required": False,
                "allow_blank": True,
            },
            "remarks": {
                "required": False,
                "allow_blank": True,
            },
        }

    def validate_file(self, file_obj):
        request = self.context["request"]
        target_user = self.context["target_user"]

        allowed_owner_ids = {
            request.user.id,
            target_user.id,
            None,
        }

        if (
            file_obj.uploaded_by_id not in allowed_owner_ids
            and not request.user.is_superuser
        ):
            raise serializers.ValidationError(
                "This file belongs to another user."
            )

        if not file_obj.file:
            raise serializers.ValidationError(
                "The selected file is unavailable."
            )

        return file_obj

    def validate_document_type(self, value):
        document_type = str(value or "").strip().lower()

        if document_type not in self.ALLOWED_DOCUMENT_TYPES:
            raise serializers.ValidationError(
                "Unsupported document type."
            )

        return document_type

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one document field must be provided."
            )

        instance = self.instance
        target_user = self.context["target_user"]

        document_type = attrs.get(
            "document_type",
            getattr(instance, "document_type", None),
        )

        file_obj = attrs.get(
            "file",
            getattr(instance, "file", None),
        )

        if self.instance is None:
            if not document_type:
                raise serializers.ValidationError({
                    "document_type": (
                        "Document type is required."
                    )
                })

            if not file_obj:
                raise serializers.ValidationError({
                    "file": (
                        "Document file is required."
                    )
                })

        if not document_type:
            raise serializers.ValidationError({
                "document_type": (
                    "Document type is required."
                )
            })

        document_type = str(
            document_type
        ).strip().lower()

        if (
            document_type
            not in self.ALLOWED_DOCUMENT_TYPES
        ):
            raise serializers.ValidationError({
                "document_type": (
                    "Unsupported document type."
                )
            })

        self._validate_document_type_for_role(
            target_user=target_user,
            document_type=document_type,
        )

        self._normalize_conditional_fields(
            attrs=attrs,
            document_type=document_type,
        )

        issued_date = attrs.get(
            "issued_date",
            getattr(instance, "issued_date", None),
        )

        expiry_date = attrs.get(
            "expiry_date",
            getattr(instance, "expiry_date", None),
        )

        if (
            issued_date
            and expiry_date
            and expiry_date < issued_date
        ):
            raise serializers.ValidationError({
                "expiry_date": (
                    "Expiry date cannot be earlier "
                    "than issued date."
                )
            })

        return attrs

    def _validate_document_type_for_role(
        self,
        *,
        target_user,
        document_type,
    ):
        role = str(
            getattr(target_user, "role", "") or ""
        ).strip().lower()

        if (
            role == "student"
            and document_type
            not in self.STUDENT_ALLOWED_DOCUMENT_TYPES
        ):
            raise serializers.ValidationError({
                "document_type": (
                    "Students may only have Photo, "
                    "Birth Certificate, Transfer Certificate, "
                    "or Marksheet documents."
                )
            })

    def _normalize_conditional_fields(
        self,
        *,
        attrs,
        document_type,
    ):
        """
        Clear unsupported metadata fields.

        This handles both create and partial update cases.

        For example, if a passport is changed to a photo,
        the old expiry date should not remain in the database.
        """

        has_details = (
            document_type
            in self.DOCUMENT_TYPES_WITH_DETAILS
        )

        has_expiry = (
            document_type
            in self.DOCUMENT_TYPES_WITH_EXPIRY
        )

        if not has_details:
            attrs["issued_by"] = ""
            attrs["issued_date"] = None
            attrs["remarks"] = ""

        if not has_expiry:
            attrs["expiry_date"] = None

    @transaction.atomic
    def create(self, validated_data):
        profile = self.context["profile"]
        file_obj = validated_data["file"]

        document = ProfileDocument.objects.create(
            profile=profile,
            **validated_data,
        )

        self._finalize_uploaded_file(
            file_obj=file_obj,
            owner=profile.user,
        )

        return document

    @transaction.atomic
    def update(
        self,
        instance,
        validated_data,
    ):
        document = super().update(
            instance,
            validated_data,
        )

        file_obj = validated_data.get("file")

        if file_obj:
            self._finalize_uploaded_file(
                file_obj=file_obj,
                owner=instance.profile.user,
            )

        return document

    @staticmethod
    def _finalize_uploaded_file(
        *,
        file_obj,
        owner,
    ):
        update_fields = []

        if file_obj.is_temporary:
            file_obj.is_temporary = False
            update_fields.append(
                "is_temporary"
            )

        if file_obj.uploaded_by_id is None:
            file_obj.uploaded_by = owner
            update_fields.append(
                "uploaded_by"
            )

        if update_fields:
            file_obj.save(
                update_fields=update_fields
            )

class StudentHealthSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentOtherInfo
        fields = [
            "id",
            "is_disabled",
            "disability_details",
            "visual_issues",
            "hearing_issues",
            "mobility_issues",
            "chronic_illness",
            "chronic_illness_details",
            "allergies",
            "allergy_details",
            "medications",
            "medication_details",
            "dietary_restrictions",
            "dietary_restriction_details",
            "other_health_issues",
            "other_health_issue_details",
        ]
        read_only_fields = ["id"]


class StudentHealthUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentOtherInfo
        fields = [
            "is_disabled",
            "disability_details",
            "visual_issues",
            "hearing_issues",
            "mobility_issues",
            "chronic_illness",
            "chronic_illness_details",
            "allergies",
            "allergy_details",
            "medications",
            "medication_details",
            "dietary_restrictions",
            "dietary_restriction_details",
            "other_health_issues",
            "other_health_issue_details",
        ]
        extra_kwargs = {
            field: {"required": False}
            for field in fields
        }

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one health field must be provided."
            )

        detail_dependencies = [
            (
                "is_disabled",
                "disability_details",
                "Disability details are required when disabled is true.",
            ),
            (
                "chronic_illness",
                "chronic_illness_details",
                "Chronic illness details are required when chronic illness is true.",
            ),
            (
                "allergies",
                "allergy_details",
                "Allergy details are required when allergies is true.",
            ),
            (
                "medications",
                "medication_details",
                "Medication details are required when medications is true.",
            ),
            (
                "dietary_restrictions",
                "dietary_restriction_details",
                "Dietary restriction details are required when restrictions are true.",
            ),
            (
                "other_health_issues",
                "other_health_issue_details",
                "Other health issue details are required when enabled.",
            ),
        ]

        errors = {}

        for boolean_field, detail_field, message in detail_dependencies:
            boolean_value = attrs.get(
                boolean_field,
                getattr(self.instance, boolean_field, False),
            )

            detail_value = attrs.get(
                detail_field,
                getattr(self.instance, detail_field, ""),
            )

            if boolean_value and not str(detail_value).strip():
                errors[detail_field] = message

            if boolean_field in attrs and attrs[boolean_field] is False:
                attrs[detail_field] = ""

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class ManagementCompleteProfileSerializer(serializers.Serializer):
    user = ManagementUserSummarySerializer()
    personal_info = PersonalInfoSerializer(allow_null=True)
    permanent_address = AddressSerializer(allow_null=True)
    temporary_address = AddressSerializer(allow_null=True)
    current_address = AddressSerializer(allow_null=True)
    guardians = GuardianSerializer(many=True)
    documents = ProfileDocumentSerializer(many=True)
    health = StudentHealthSerializer(allow_null=True)