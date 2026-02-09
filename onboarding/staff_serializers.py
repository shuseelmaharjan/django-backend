from __future__ import annotations

import secrets
import string
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from accounts.models import User
from profiles.models import Profile, Address, ProfileDocument, DocumentType
from filehandler.models import UploadedFile  # adjust import if different
from common.constants import UserRole, UserStatus

from utils.get_school_id_by_token import get_school_for_user
from utils.email_validator import validate_unique_email
from utils.phone_validator import clean_and_validate_phone
from utils.usernames import build_base_username, make_unique_username
from rest_framework.exceptions import ValidationError

from smtp.services import send_html_template_email  # adjust to your function
import logging

logger = logging.getLogger(__name__)

ALLOWED_STAFF_ROLES = {
    UserRole.VICE_PRINCIPAL,
    UserRole.TEACHER,
    UserRole.COORDINATOR,
    UserRole.ACCOUNTANT,
    UserRole.CASHIER,
}


def generate_temp_password(length: int = 10) -> str:
    # simple strong temp password
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class StaffUserPayloadSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32)
    email = serializers.EmailField(required=False, allow_blank=True, default="")


class StaffProfilePayloadSerializer(serializers.Serializer):
    date_of_birth_ad = serializers.DateField(required=False, allow_null=True)
    date_of_birth_bs = serializers.CharField(required=False, allow_blank=True, default="")
    gender = serializers.ChoiceField(choices=Profile._meta.get_field("gender").choices, required=False, allow_blank=True)
    blood_group = serializers.ChoiceField(choices=Profile._meta.get_field("blood_group").choices, required=False)
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


class DocumentItemSerializer(serializers.Serializer):
    file = serializers.UUIDField()
    issued_by = serializers.CharField(required=False, allow_blank=True, default="")
    issued_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class StaffCreateUpdateSerializer(serializers.Serializer):
    """
    Request format:
    {
      "role": "teacher",
      "user": {...},
      "profile": {...},
      "addresses": [...],
      "documents": { "photo": {...}, "pan": {...} }
    }
    """

    role = serializers.ChoiceField(choices=[(r, r) for r in ALLOWED_STAFF_ROLES])

    user = StaffUserPayloadSerializer()
    profile = StaffProfilePayloadSerializer(required=False)
    addresses = AddressPayloadSerializer(many=True, required=False)
    documents = serializers.DictField(child=DocumentItemSerializer(), required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        role = attrs["role"]
        if role not in ALLOWED_STAFF_ROLES:
            raise serializers.ValidationError({"role": ["Role not allowed."]})

        user_data = attrs["user"]
        phone_raw = user_data.get("phone", "")
        email_raw = user_data.get("email", "")

        # phone normalize + validate
        try:
            phone = clean_and_validate_phone(phone_raw)
        except Exception as e:
            raise serializers.ValidationError({"user": {"phone": [str(e)]}})

        # unique phone (respect soft delete)
        if User.all_objects.filter(phone=phone, is_deleted=False).exists():
            raise serializers.ValidationError({"user": {"phone": ["Phone already exists."]}})

        # unique email
        try:
            email = validate_unique_email(email_raw, User, exclude_user_id=None)
        except Exception as e:
            raise serializers.ValidationError({"user": {"email": [str(e)]}})

        user_data["phone"] = phone
        user_data["email"] = email

        # addresses: allow max 1 primary
        addresses = attrs.get("addresses") or []
        if sum(1 for a in addresses if a.get("is_primary")) > 1:
            raise serializers.ValidationError({"addresses": ["Only one address can be primary."]})

        # documents keys must be valid DocumentType
        docs = attrs.get("documents") or {}
        for k in docs.keys():
            if k not in [x[0] for x in DocumentType.choices]:
                raise serializers.ValidationError({"documents": [f"Invalid document type: {k}"]})

        attrs["_school"] = school
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> "User":
        request = self.context["request"]
        school = validated_data["_school"]

        user_data = validated_data["user"]
        profile_data = validated_data.get("profile") or {}
        addresses_data = validated_data.get("addresses") or []
        documents_data = validated_data.get("documents") or {}

        role = validated_data["role"]
        is_teacher = (role == "teacher")

        # username
        base = build_base_username(
            user_data.get("first_name", ""),
            user_data.get("middle_name", ""),
            user_data.get("last_name", ""),
        )

        def _exists(u: str) -> bool:
            return User.all_objects.filter(username__iexact=u, is_deleted=False).exists()

        username = make_unique_username(base, _exists)

        # password
        temp_password = generate_temp_password()

        # ✅ status rule (teacher -> DRAFT, others -> ACTIVE)
        status_value = UserStatus.DRAFT if is_teacher else UserStatus.ACTIVE

        # optional but recommended: draft users shouldn't be able to login
        is_active_value = False if is_teacher else True

        # create user
        user = User.objects.create_user(
            phone=user_data["phone"],
            password=temp_password,
            username=username,
            email=user_data.get("email", ""),
            first_name=user_data.get("first_name", ""),
            middle_name=user_data.get("middle_name", ""),
            last_name=user_data.get("last_name", ""),
            role=role,
            status=status_value,
            is_active=is_active_value,
        )

        # create profile
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

        # ✅ send credentials only if staff is ACTIVE (i.e., not teacher draft)
        email = user.email
        if email and not is_teacher:
            subject = "Your admin account credentials"

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
                    logger.exception(
                        "Failed to send onboarding credentials email",
                        extra={"user_id": str(user.id), "email": email},
                    )

            transaction.on_commit(_safe_send)

        return user


class StaffUpdateSerializer(serializers.Serializer):
    # ✅ role removed: cannot change role on update
    user = StaffUserPayloadSerializer(required=False)
    profile = StaffProfilePayloadSerializer(required=False)
    addresses = AddressPayloadSerializer(many=True, required=False)
    documents = serializers.DictField(child=DocumentItemSerializer(), required=False)

    def validate(self, attrs):
        request = self.context["request"]
        school = get_school_for_user(request.user)
        attrs["_school"] = school
        return attrs

    @transaction.atomic
    def update(self, instance: "User", validated_data):
        school = validated_data["_school"]

        # ensure same school (via profile)
        if not hasattr(instance, "profile") or instance.profile.school_id != school.id:
            raise ValidationError({"detail": "Not allowed."})

        # ✅ hard-block role change even if someone tries to sneak it in
        if "role" in validated_data and validated_data["role"] != instance.role:
            raise ValidationError({"role": ["Role cannot be changed."]})

        # update user fields
        u = validated_data.get("user") or {}

        if "phone" in u:
            phone = clean_and_validate_phone(u["phone"])
            if User.all_objects.filter(phone=phone, is_deleted=False).exclude(pk=instance.pk).exists():
                raise ValidationError({"user": {"phone": ["Phone already exists."]}})
            instance.phone = phone

        if "email" in u:
            instance.email = validate_unique_email(u["email"], User, exclude_user_id=instance.pk)

        for f in ("first_name", "middle_name", "last_name"):
            if f in u:
                setattr(instance, f, u.get(f, "") or "")

        instance.save()

        # profile update (create if missing)
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

        # addresses: replace all if provided
        addrs = validated_data.get("addresses")
        if addrs is not None:
            profile = instance.profile
            profile.addresses.all().delete()
            for a in addrs:
                Address.objects.create(profile=profile, **a)

        # documents: upsert per type if provided
        docs = validated_data.get("documents")
        if docs is not None:
            profile = instance.profile
            for doc_type, payload in docs.items():
                if doc_type not in [x[0] for x in DocumentType.choices]:
                    raise ValidationError({"documents": [f"Invalid document type: {doc_type}"]})

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

        return instance

class StaffUpdateSerializer(serializers.Serializer):
    role = serializers.CharField(required=False)  # optionally allow role change (validated)
    user = StaffUserPayloadSerializer(required=False)
    profile = StaffProfilePayloadSerializer(required=False)
    addresses = AddressPayloadSerializer(many=True, required=False)
    documents = serializers.DictField(child=DocumentItemSerializer(), required=False)

    def validate(self, attrs):
        request = self.context["request"]
        school = get_school_for_user(request.user)
        attrs["_school"] = school
        return attrs

    @transaction.atomic
    def update(self, instance: User, validated_data):
        school = validated_data["_school"]

        # ensure same school (via profile)
        if not hasattr(instance, "profile") or instance.profile.school_id != school.id:
            raise ValidationError({"detail": "Not allowed."})

        # update role if provided (and allowed)
        if "role" in validated_data:
            role = validated_data["role"]
            if role not in ALLOWED_STAFF_ROLES:
                raise ValidationError({"role": ["Role not allowed."]})
            instance.role = role

        # update user fields
        u = validated_data.get("user") or {}
        if "phone" in u:
            phone = clean_and_validate_phone(u["phone"])
            # uniqueness excluding self (respect soft delete)
            if User.all_objects.filter(phone=phone, is_deleted=False).exclude(pk=instance.pk).exists():
                raise ValidationError({"user": {"phone": ["Phone already exists."]}})
            instance.phone = phone

        if "email" in u:
            instance.email = validate_unique_email(u["email"], User, exclude_user_id=instance.pk)

        for f in ("first_name", "middle_name", "last_name"):
            if f in u:
                setattr(instance, f, u.get(f, "") or "")

        instance.save()

        # profile update (create if missing)
        p = validated_data.get("profile")
        if p is not None:
            profile, _ = Profile.objects.get_or_create(user=instance, defaults={"school": school})
            # keep school correct
            if profile.school_id != school.id:
                profile.school = school

            if "date_of_birth_ad" in p:
                profile.date_of_birth_in_ad = p.get("date_of_birth_ad")
            if "date_of_birth_bs" in p:
                profile.date_of_birth_in_bs = p.get("date_of_birth_bs", "") or ""
            for f_map in [
                ("gender", "gender"),
                ("blood_group", "blood_group"),
                ("nationality", "nationality"),
                ("religion", "religion"),
                ("mother_tongue", "mother_tongue"),
                ("citizenship_no", "citizenship_no"),
                ("pan_no", "pan_no"),
            ]:
                src, dst = f_map
                if src in p:
                    setattr(profile, dst, p.get(src, "") or "")

            profile.save()

        # addresses: if provided, replace all (simple + predictable)
        addrs = validated_data.get("addresses")
        if addrs is not None:
            profile = instance.profile
            profile.addresses.all().delete()
            for a in addrs:
                Address.objects.create(profile=profile, **a)

        # documents: if provided, upsert per type (replace existing type)
        docs = validated_data.get("documents")
        if docs is not None:
            profile = instance.profile
            for doc_type, payload in docs.items():
                if doc_type not in [x[0] for x in DocumentType.choices]:
                    raise ValidationError({"documents": [f"Invalid document type: {doc_type}"]})

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

        return instance