# onboarding/serializers.py
from __future__ import annotations

from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from profiles.models import Profile, AddressType
from schools.models import School
from utils.dates import bs_to_ad, ad_to_bs
from utils.phone_validator import clean_and_validate_phone

User = get_user_model()


# -----------------------
# CREATE serializers
# -----------------------

class OnboardingUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32)
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    def validate_phone(self, value: str) -> str:
        try:
            return clean_and_validate_phone(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)

    def validate_email(self, value: str) -> str:
        value = (value or "").strip().lower()
        if not value:
            return value
        # alive-only uniqueness (User.objects is SoftDeleteManager)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value


class OnboardingSchoolSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=50)
    name = serializers.CharField(max_length=150)

    address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    logo_file = serializers.UUIDField(required=False, allow_null=True)
    pan_number = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    registration_number = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    pan_document_file = serializers.UUIDField(required=False, allow_null=True)
    registration_document_file = serializers.UUIDField(required=False, allow_null=True)

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        try:
            return clean_and_validate_phone(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)


class OnboardingProfileSerializer(serializers.Serializer):
    date_of_birth_bs = serializers.CharField(required=False, allow_blank=True, default="")
    date_of_birth_ad = serializers.DateField(required=False, allow_null=True)

    gender = serializers.ChoiceField(
        choices=[c[0] for c in Profile._meta.get_field("gender").choices],
        required=False,
        allow_blank=True,
        default="",
    )
    blood_group = serializers.ChoiceField(
        choices=[c[0] for c in Profile._meta.get_field("blood_group").choices]
    )

    nationality = serializers.CharField(max_length=60)
    religion = serializers.CharField(max_length=60)
    mother_tongue = serializers.CharField(max_length=60)

    citizenship_no = serializers.CharField(max_length=80)
    pan_no = serializers.CharField(max_length=40)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        bs = (attrs.get("date_of_birth_bs") or "").strip()
        ad = attrs.get("date_of_birth_ad")

        if not bs and not ad:
            raise serializers.ValidationError({
                "date_of_birth_bs": ["Provide date_of_birth_bs or date_of_birth_ad."],
                "date_of_birth_ad": ["Provide date_of_birth_bs or date_of_birth_ad."]
            })

        if bs:
            try:
                ad_date = bs_to_ad(bs)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"date_of_birth_bs": e.messages})
            attrs["date_of_birth_in_ad"] = ad_date
            attrs["date_of_birth_in_bs"] = bs
        else:
            try:
                bs_str = ad_to_bs(ad)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"date_of_birth_ad": e.messages})
            attrs["date_of_birth_in_ad"] = ad
            attrs["date_of_birth_in_bs"] = bs_str

        return attrs


class OnboardingAddressSerializer(serializers.Serializer):
    address_type = serializers.ChoiceField(choices=AddressType.choices)

    province = serializers.CharField(max_length=80)
    district = serializers.CharField(max_length=80)
    municipality = serializers.CharField(max_length=80)
    ward_no = serializers.CharField(max_length=20)

    country = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    street = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    tole = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    house_no = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    is_primary = serializers.BooleanField(required=False, default=False)


class OnboardingDocumentItemSerializer(serializers.Serializer):
    file = serializers.UUIDField()
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    issued_by = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    issued_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)


class OnboardingDocumentsSerializer(serializers.Serializer):
    photo = OnboardingDocumentItemSerializer()
    citizenship_front = OnboardingDocumentItemSerializer()
    citizenship_back = OnboardingDocumentItemSerializer()
    pan = OnboardingDocumentItemSerializer()
    signature = OnboardingDocumentItemSerializer()


class AdminOnboardingCreateSerializer(serializers.Serializer):
    user = OnboardingUserSerializer()
    school = OnboardingSchoolSerializer()
    profile = OnboardingProfileSerializer()
    addresses = OnboardingAddressSerializer(many=True)
    documents = OnboardingDocumentsSerializer()

    def validate_addresses(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(value) != 2:
            raise serializers.ValidationError("Must include exactly two addresses: permanent and temporary.")

        seen = set()
        for idx, item in enumerate(value):
            at = item.get("address_type")
            if at in seen:
                raise serializers.ValidationError({idx: {"address_type": ["Duplicate address_type."]}})
            seen.add(at)

        required = {AddressType.PERMANENT, AddressType.TEMPORARY}
        missing = required - seen
        extra = seen - required
        if missing:
            raise serializers.ValidationError(f"Missing address types: {sorted(list(missing))}")
        if extra:
            raise serializers.ValidationError(f"Unexpected address types: {sorted(list(extra))}")

        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        code = attrs["school"]["code"]
        if School.objects.filter(code=code).exists():
            raise serializers.ValidationError({"school": {"code": ["School code already exists."]}})
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        from .services import onboard_admin_user_and_school
        return onboard_admin_user_and_school(validated_data=validated_data)


# -----------------------
# READ serializer
# -----------------------

class AdminOnboardingReadSerializer(serializers.Serializer):
    user = serializers.DictField()
    school = serializers.DictField(allow_null=True)
    profile = serializers.DictField(allow_null=True)
    addresses = serializers.ListField(child=serializers.DictField())
    documents = serializers.DictField()


class AdminOnboardingListSerializer(serializers.Serializer):
    results = AdminOnboardingReadSerializer(many=True)


# -----------------------
# UPDATE serializers
# -----------------------

class OnboardingUserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    middle_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=32, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate_phone(self, value: str) -> str:
        try:
            return clean_and_validate_phone(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)

    def validate_email(self, value: str) -> str:
        return (value or "").strip().lower()


class OnboardingSchoolUpdateSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=50, required=False)
    name = serializers.CharField(max_length=150, required=False)

    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    logo_file = serializers.UUIDField(required=False, allow_null=True)
    pan_number = serializers.CharField(max_length=40, required=False, allow_blank=True)
    registration_number = serializers.CharField(max_length=80, required=False, allow_blank=True)
    pan_document_file = serializers.UUIDField(required=False, allow_null=True)
    registration_document_file = serializers.UUIDField(required=False, allow_null=True)

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        try:
            return clean_and_validate_phone(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)


class OnboardingProfileUpdateSerializer(serializers.Serializer):
    date_of_birth_bs = serializers.CharField(required=False, allow_blank=True)
    date_of_birth_ad = serializers.DateField(required=False, allow_null=True)

    gender = serializers.ChoiceField(
        choices=[c[0] for c in Profile._meta.get_field("gender").choices],
        required=False,
        allow_blank=True,
    )
    blood_group = serializers.ChoiceField(
        choices=[c[0] for c in Profile._meta.get_field("blood_group").choices],
        required=False,
    )

    nationality = serializers.CharField(max_length=60, required=False)
    religion = serializers.CharField(max_length=60, required=False)
    mother_tongue = serializers.CharField(max_length=60, required=False)

    citizenship_no = serializers.CharField(max_length=80, required=False)
    pan_no = serializers.CharField(max_length=40, required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        bs_provided = "date_of_birth_bs" in attrs
        ad_provided = "date_of_birth_ad" in attrs
        if not bs_provided and not ad_provided:
            return attrs

        bs = (attrs.get("date_of_birth_bs") or "").strip() if bs_provided else ""
        ad = attrs.get("date_of_birth_ad") if ad_provided else None

        if bs:
            try:
                attrs["date_of_birth_in_ad"] = bs_to_ad(bs)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"date_of_birth_bs": e.messages})
            attrs["date_of_birth_in_bs"] = bs
        else:
            if ad is None:
                raise serializers.ValidationError({"date_of_birth_ad": ["Provide date_of_birth_ad if date_of_birth_bs is blank."]})
            try:
                attrs["date_of_birth_in_bs"] = ad_to_bs(ad)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"date_of_birth_ad": e.messages})
            attrs["date_of_birth_in_ad"] = ad

        return attrs


class OnboardingAddressUpdateSerializer(serializers.Serializer):
    address_type = serializers.ChoiceField(choices=AddressType.choices)

    province = serializers.CharField(max_length=80, required=False)
    district = serializers.CharField(max_length=80, required=False)
    municipality = serializers.CharField(max_length=80, required=False)
    ward_no = serializers.CharField(max_length=20, required=False)

    country = serializers.CharField(max_length=80, required=False, allow_blank=True)
    street = serializers.CharField(max_length=120, required=False, allow_blank=True)
    tole = serializers.CharField(max_length=120, required=False, allow_blank=True)
    house_no = serializers.CharField(max_length=40, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(required=False)


class OnboardingDocumentItemUpdateSerializer(serializers.Serializer):
    file = serializers.UUIDField(required=False)
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True)
    issued_by = serializers.CharField(max_length=120, required=False, allow_blank=True)
    issued_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)


class OnboardingDocumentsUpdateSerializer(serializers.Serializer):
    photo = OnboardingDocumentItemUpdateSerializer(required=False)
    citizenship_front = OnboardingDocumentItemUpdateSerializer(required=False)
    citizenship_back = OnboardingDocumentItemUpdateSerializer(required=False)
    pan = OnboardingDocumentItemUpdateSerializer(required=False)
    signature = OnboardingDocumentItemUpdateSerializer(required=False)


class AdminOnboardingUpdateSerializer(serializers.Serializer):
    user = OnboardingUserUpdateSerializer(required=False)
    school = OnboardingSchoolUpdateSerializer(required=False)
    profile = OnboardingProfileUpdateSerializer(required=False)
    addresses = OnboardingAddressUpdateSerializer(many=True, required=False)
    documents = OnboardingDocumentsUpdateSerializer(required=False)
