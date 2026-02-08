from __future__ import annotations

import logging
import secrets
import string
from typing import Any

from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from accounts.models import User
from profiles.models import (
    Profile,
    Address,
    Guardian,
    GuardianRelation,
    ProfileDocument,
    DocumentType,
    StudentOtherInfo,
)
from filehandler.models import UploadedFile
from common.constants import UserStatus

from utils.get_school_id_by_token import get_school_for_user
from utils.email_validator import validate_unique_email
from utils.phone_validator import clean_and_validate_phone
from utils.usernames import build_base_username, make_unique_username

from smtp.services import send_html_template_email

logger = logging.getLogger(__name__)

STUDENT_ROLE_VALUE = "student"  # ✅ do NOT use UserRole.STUDENT (it doesn't exist)

REQUIRED_STUDENT_DOCS = {"photo", "birth_certificate"}
OPTIONAL_STUDENT_DOCS = {"transfer_certificate", "marksheet"}
ALLOWED_STUDENT_DOCS = REQUIRED_STUDENT_DOCS | OPTIONAL_STUDENT_DOCS


def generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class StudentUserPayloadSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32)
    email = serializers.EmailField(required=False, allow_blank=True, default="")  # optional


class StudentProfilePayloadSerializer(serializers.Serializer):
    date_of_birth_ad = serializers.DateField(required=False, allow_null=True)
    date_of_birth_bs = serializers.CharField(required=False, allow_blank=True, default="")
    gender = serializers.ChoiceField(
        choices=Profile._meta.get_field("gender").choices, required=False, allow_blank=True
    )
    blood_group = serializers.ChoiceField(
        choices=Profile._meta.get_field("blood_group").choices, required=False
    )
    nationality = serializers.CharField(required=False, allow_blank=True, default="")
    religion = serializers.CharField(required=False, allow_blank=True, default="")
    mother_tongue = serializers.CharField(required=False, allow_blank=True, default="")
    citizenship_no = serializers.CharField(required=False, allow_blank=True, default="")
    pan_no = serializers.CharField(required=False, allow_blank=True, default="")


class AddressPayloadSerializer(serializers.Serializer):
    address_type = serializers.ChoiceField(choices=Address._meta.get_field("address_type").choices)
    country = serializers.CharField(required=False, allow_blank=True, default="")
    province = serializers.CharField(required=False, allow_blank=True, default="")
    district = serializers.CharField(required=False, allow_blank=True, default="")
    municipality = serializers.CharField(required=False, allow_blank=True, default="")
    ward_no = serializers.CharField(required=False, allow_blank=True, default="")
    street = serializers.CharField(required=False, allow_blank=True, default="")
    tole = serializers.CharField(required=False, allow_blank=True, default="")
    house_no = serializers.CharField(required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(required=False, allow_blank=True, default="")
    is_primary = serializers.BooleanField(default=False)


class GuardianPayloadSerializer(serializers.Serializer):
    """
    Require at least 1 guardian. Allow up to 4.
    """
    id = serializers.UUIDField(required=False)  # optional for PUT-like updates if you want later
    relation = serializers.ChoiceField(choices=GuardianRelation.choices)
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    occupation = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    is_primary = serializers.BooleanField(default=False)


class DocumentItemSerializer(serializers.Serializer):
    file = serializers.UUIDField()
    issued_by = serializers.CharField(required=False, allow_blank=True, default="")
    issued_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class StudentOtherInfoPayloadSerializer(serializers.Serializer):
    is_disabled = serializers.BooleanField()
    disability_details = serializers.CharField(max_length=255, allow_blank=True)
    visual_issues = serializers.BooleanField()
    hearing_issues = serializers.BooleanField()
    mobility_issues = serializers.BooleanField()
    chronic_illness = serializers.BooleanField()
    chronic_illness_details = serializers.CharField(max_length=255, allow_blank=True)
    allergies = serializers.BooleanField()
    allergy_details = serializers.CharField(max_length=255, allow_blank=True)
    medications = serializers.BooleanField()
    medication_details = serializers.CharField(max_length=255, allow_blank=True)
    dietary_restrictions = serializers.BooleanField()
    dietary_restriction_details = serializers.CharField(max_length=255, allow_blank=True)
    other_health_issues = serializers.BooleanField()
    other_health_issue_details = serializers.CharField(max_length=255, allow_blank=True)


class StudentCreateUpdateSerializer(serializers.Serializer):
    user = StudentUserPayloadSerializer()
    profile = StudentProfilePayloadSerializer(required=False)
    addresses = AddressPayloadSerializer(many=True, required=False)

    # ✅ guardians required (min 1, max 4)
    guardians = GuardianPayloadSerializer(many=True, required=True)

    documents = serializers.DictField(child=DocumentItemSerializer(), required=True)
    other_info = StudentOtherInfoPayloadSerializer(required=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        user_data = attrs["user"]
        phone_raw = user_data.get("phone", "")
        email_raw = (user_data.get("email") or "").strip()

        # phone normalize + validate
        try:
            phone = clean_and_validate_phone(phone_raw)
        except Exception as e:
            raise serializers.ValidationError({"user": {"phone": [str(e)]}})

        if User.all_objects.filter(phone=phone, is_deleted=False).exists():
            raise serializers.ValidationError({"user": {"phone": ["Phone already exists."]}})

        # email optional; if provided -> validate uniqueness
        if email_raw:
            try:
                email = validate_unique_email(email_raw, User, exclude_user_id=None)
            except Exception as e:
                raise serializers.ValidationError({"user": {"email": [str(e)]}})
        else:
            email = ""

        user_data["phone"] = phone
        user_data["email"] = email

        # addresses: allow max 1 primary
        addresses = attrs.get("addresses") or []
        if sum(1 for a in addresses if a.get("is_primary")) > 1:
            raise serializers.ValidationError({"addresses": ["Only one address can be primary."]})

        # ✅ guardians: min 1, max 4
        guardians = attrs.get("guardians") or []
        if len(guardians) < 1:
            raise serializers.ValidationError({"guardians": ["At least 1 guardian is required."]})
        if len(guardians) > 4:
            raise serializers.ValidationError({"guardians": ["Maximum 4 guardians allowed."]})

        # optional: enforce max 1 primary guardian
        if sum(1 for g in guardians if g.get("is_primary")) > 1:
            raise serializers.ValidationError({"guardians": ["Only one guardian can be primary."]})

        # documents: enforce allowed keys + required docs presence
        docs = attrs.get("documents") or {}
        invalid_keys = [k for k in docs.keys() if k not in ALLOWED_STUDENT_DOCS]
        if invalid_keys:
            raise serializers.ValidationError({"documents": [f"Invalid document type(s): {', '.join(invalid_keys)}"]})

        missing_required = [k for k in REQUIRED_STUDENT_DOCS if k not in docs]
        if missing_required:
            raise serializers.ValidationError({"documents": [f"Missing required document(s): {', '.join(missing_required)}"]})

        valid_choice_keys = {x[0] for x in DocumentType.choices}
        for k in docs.keys():
            if k not in valid_choice_keys:
                raise serializers.ValidationError({"documents": [f"DocumentType choice not configured for: {k}"]})

        attrs["_school"] = school
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> User:
        school = validated_data["_school"]

        user_data = validated_data["user"]
        profile_data = validated_data.get("profile") or {}
        addresses_data = validated_data.get("addresses") or []
        guardians_data = validated_data.get("guardians") or []
        documents_data = validated_data.get("documents") or {}
        other_info_data = validated_data["other_info"]

        base = build_base_username(
            user_data.get("first_name", ""),
            user_data.get("middle_name", ""),
            user_data.get("last_name", ""),
        )

        def _exists(u: str) -> bool:
            return User.all_objects.filter(username__iexact=u, is_deleted=False).exists()

        username = make_unique_username(base, _exists)
        temp_password = generate_temp_password()

        user = User.objects.create_user(
            phone=user_data["phone"],
            password=temp_password,
            username=username,
            email=user_data.get("email", ""),
            first_name=user_data.get("first_name", ""),
            middle_name=user_data.get("middle_name", ""),
            last_name=user_data.get("last_name", ""),
            role=STUDENT_ROLE_VALUE,     # ✅ fixed
            status=UserStatus.DRAFT,
            is_active=True,
        )

        profile = Profile.objects.create(
            school=school,
            user=user,
            date_of_birth_in_ad=profile_data.get("date_of_birth_ad"),
            date_of_birth_in_bs=profile_data.get("date_of_birth_bs", ""),
            gender=profile_data.get("gender", ""),
            blood_group=profile_data.get("blood_group", "unknown"),
            nationality=profile_data.get("nationality", ""),
            religion=profile_data.get("religion", ""),
            mother_tongue=profile_data.get("mother_tongue", ""),
            citizenship_no=profile_data.get("citizenship_no", ""),
            pan_no=profile_data.get("pan_no", ""),
        )

        # other info
        StudentOtherInfo.objects.create(profile=profile, **other_info_data)

        # ✅ guardians (required)
        for g in guardians_data:
            Guardian.objects.create(profile=profile, **g)

        # addresses
        for a in addresses_data:
            Address.objects.create(profile=profile, **a)

        # documents
        for doc_type, payload in documents_data.items():
            file_id = payload.get("file")
            if not UploadedFile.objects.filter(id=file_id).exists():
                raise serializers.ValidationError({"documents": {doc_type: ["Invalid file id."]}})

            ProfileDocument.objects.create(
                profile=profile,
                document_type=doc_type,
                file_id=file_id,
                issued_by=payload.get("issued_by", ""),
                issued_date=payload.get("issued_date"),
                expiry_date=payload.get("expiry_date"),
                remarks=payload.get("remarks", ""),
            )

        # email credentials only if email provided
        email = user.email
        if email:
            subject = "Your student account credentials"
            context = {
                "first_name": user.first_name,
                "phone": user.phone,
                "username": user.username,
                "password": temp_password,
                "app_name": settings.APP_NAME,
            }
            text_fallback = (
                f"Hi {user.first_name},\n\n"
                f"Login (phone): {user.phone}\n"
                f"Username: {user.username}\n"
                f"Password: {temp_password}\n\n"
                f"Please change your password after login."
            )

            def _safe_send():
                try:
                    send_html_template_email(
                        subject=subject,
                        template_name="smtp/onboarding_credentials.html",
                        context=context,
                        recipients=[email],
                        text_fallback=text_fallback,
                    )
                except Exception:
                    logger.exception("Failed to send onboarding credentials email", extra={"user_id": str(user.id), "email": email})

            transaction.on_commit(_safe_send)

        return user


class StudentUpdateSerializer(serializers.Serializer):
    user = StudentUserPayloadSerializer(required=False)
    profile = StudentProfilePayloadSerializer(required=False)
    addresses = AddressPayloadSerializer(many=True, required=False)

    # ✅ allow updating guardians too (optional)
    guardians = GuardianPayloadSerializer(many=True, required=False)

    documents = serializers.DictField(child=DocumentItemSerializer(), required=False)
    other_info = StudentOtherInfoPayloadSerializer(required=False)

    def validate(self, attrs):
        request = self.context["request"]
        attrs["_school"] = get_school_for_user(request.user)
        return attrs

    @transaction.atomic
    def update(self, instance: User, validated_data):
        school = validated_data["_school"]

        if not hasattr(instance, "profile") or instance.profile.school_id != school.id:
            raise ValidationError({"detail": "Not allowed."})

        if instance.role != STUDENT_ROLE_VALUE:
            raise ValidationError({"detail": "Not a student user."})

        u = validated_data.get("user") or {}
        if "phone" in u:
            phone = clean_and_validate_phone(u["phone"])
            if User.all_objects.filter(phone=phone, is_deleted=False).exclude(pk=instance.pk).exists():
                raise ValidationError({"user": {"phone": ["Phone already exists."]}})
            instance.phone = phone

        if "email" in u:
            email_raw = (u.get("email") or "").strip()
            if email_raw:
                instance.email = validate_unique_email(email_raw, User, exclude_user_id=instance.pk)
            else:
                instance.email = ""

        for f in ("first_name", "middle_name", "last_name"):
            if f in u:
                setattr(instance, f, u.get(f, "") or "")

        instance.save()

        p = validated_data.get("profile")
        if p is not None:
            profile, _ = Profile.objects.get_or_create(user=instance, defaults={"school": school})
            if profile.school_id != school.id:
                profile.school = school

            if "date_of_birth_ad" in p:
                profile.date_of_birth_in_ad = p.get("date_of_birth_ad")
            if "date_of_birth_bs" in p:
                profile.date_of_birth_in_bs = p.get("date_of_birth_bs", "") or ""

            for src, dst in [
                ("gender", "gender"),
                ("blood_group", "blood_group"),
                ("nationality", "nationality"),
                ("religion", "religion"),
                ("mother_tongue", "mother_tongue"),
                ("citizenship_no", "citizenship_no"),
                ("pan_no", "pan_no"),
            ]:
                if src in p:
                    setattr(profile, dst, p.get(src, "") or "")
            profile.save()

        addrs = validated_data.get("addresses")
        if addrs is not None:
            profile = instance.profile
            profile.addresses.all().delete()
            for a in addrs:
                Address.objects.create(profile=profile, **a)

        # ✅ guardians: if provided, replace ALL guardians (simple & predictable)
        gs = validated_data.get("guardians")
        if gs is not None:
            if len(gs) < 1:
                raise ValidationError({"guardians": ["At least 1 guardian is required."]})
            if len(gs) > 4:
                raise ValidationError({"guardians": ["Maximum 4 guardians allowed."]})
            if sum(1 for g in gs if g.get("is_primary")) > 1:
                raise ValidationError({"guardians": ["Only one guardian can be primary."]})

            profile = instance.profile
            profile.guardians.all().delete()
            for g in gs:
                Guardian.objects.create(profile=profile, **g)

        docs = validated_data.get("documents")
        if docs is not None:
            invalid_keys = [k for k in docs.keys() if k not in ALLOWED_STUDENT_DOCS]
            if invalid_keys:
                raise ValidationError({"documents": [f"Invalid document type(s): {', '.join(invalid_keys)}"]})

            profile = instance.profile
            valid_choice_keys = {x[0] for x in DocumentType.choices}
            for doc_type, payload in docs.items():
                if doc_type not in valid_choice_keys:
                    raise ValidationError({"documents": [f"DocumentType choice not configured for: {doc_type}"]})

                file_id = payload.get("file")
                if not UploadedFile.objects.filter(id=file_id).exists():
                    raise ValidationError({"documents": {doc_type: ["Invalid file id."]}})

                ProfileDocument.objects.update_or_create(
                    profile=profile,
                    document_type=doc_type,
                    defaults={
                        "file_id": file_id,
                        "issued_by": payload.get("issued_by", ""),
                        "issued_date": payload.get("issued_date"),
                        "expiry_date": payload.get("expiry_date"),
                        "remarks": payload.get("remarks", ""),
                    },
                )

        oi = validated_data.get("other_info")
        if oi is not None:
            profile = instance.profile
            StudentOtherInfo.objects.update_or_create(profile=profile, defaults={**oi})

        return instance
