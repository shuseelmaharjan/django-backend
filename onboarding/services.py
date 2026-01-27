# onboarding/services.py
from __future__ import annotations

import logging


from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from common.constants import UserRole, UserStatus
from profiles.models import Profile, Address, ProfileDocument, DocumentType, AddressType
from schools.models import School
from utils.phone_validator import clean_and_validate_phone
from utils.usernames import build_base_username, make_unique_username  # ✅ correct import
from filehandler.serializers import UploadedFileSerializer
from filehandler.models import UploadedFile
from common.passwords import generate_strong_password
from smtp.services import send_html_template_email
from django.conf import settings


User = get_user_model()
logger = logging.getLogger(__name__)


REQUIRED_DOC_MAP = {
    "photo": DocumentType.PHOTO,
    "citizenship_front": DocumentType.CITIZENSHIP_FRONT,
    "citizenship_back": DocumentType.CITIZENSHIP_BACK,
    "pan": DocumentType.PAN,
    "signature": DocumentType.SIGNATURE,
}

def _serialize_uploaded_file(obj: UploadedFile | None, *, request) -> dict | None:
    if not obj:
        return None
    return UploadedFileSerializer(obj, context={"request": request}).data

# -----------------------
# helpers
# -----------------------

def _username_exists_any(username: str) -> bool:
    # must include deleted due to DB unique=True on username
    return User.all_objects.filter(username=username).exists()


def _generate_unique_username(first: str, middle: str, last: str) -> str:
    base = build_base_username(first_name=first, middle_name=middle, last_name=last)
    return make_unique_username(base, _username_exists_any)


def _get_admin_user_or_404(*, user_id: str, include_deleted: bool = False) -> User:
    """
    include_deleted:
      - False: only alive users (User.objects)
      - True: include soft-deleted users (User.all_objects)
    """
    manager = User.all_objects if include_deleted else User.objects
    user = get_object_or_404(manager, id=user_id)

    if user.is_superuser or getattr(user, "role", None) != UserRole.ADMIN:
        raise serializers.ValidationError({"user_id": ["User is not an ADMIN."]})
    return user



def _get_school_for_owner_or_error(*, owner: User) -> School:
    school = School.objects.filter(owner=owner).order_by("-created_at").first()
    if not school:
        raise serializers.ValidationError({"school": {"non_field_errors": ["School not found for this admin user."]}})
    return school


def list_admin_user_ids() -> List[str]:
    qs = (
        User.objects
        .filter(role=UserRole.ADMIN)
        .exclude(is_superuser=True)
        .order_by("-date_joined")
        .values_list("id", flat=True)
    )
    return [str(x) for x in qs]


# -----------------------
# CREATE bundle
# -----------------------

@dataclass(frozen=True)
class OnboardingCreateResult:
    user_id: str
    school_id: str
    profile_id: str
    address_ids: Dict[str, str]
    document_ids: Dict[str, str]
    username: str


@transaction.atomic
def onboard_admin_user_and_school(*, validated_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates everything in one transaction, in order:
    User -> School -> Profile -> Addresses -> Documents
    """
    user_data = validated_data["user"]
    school_data = validated_data["school"]
    profile_data = validated_data["profile"]
    addresses_data = validated_data["addresses"]
    documents_data = validated_data["documents"]
    email = (user_data.get("email") or "").strip().lower()
    temp_password = generate_strong_password()

    # 1) USER
    try:
        cleaned_phone = clean_and_validate_phone(user_data["phone"])
    except DjangoValidationError as e:
        raise serializers.ValidationError({"user": {"phone": e.messages}})

    email = (user_data.get("email") or "").strip().lower()
    if email and User.objects.filter(email__iexact=email).exists():
        raise serializers.ValidationError({"user": {"email": ["Email already exists."]}})

    # phone uniqueness among alive
    if User.objects.filter(phone=cleaned_phone).exists():
        raise serializers.ValidationError({"user": {"phone": ["Phone already exists."]}})

    username = _generate_unique_username(
        first=user_data["first_name"],
        middle=user_data.get("middle_name", ""),
        last=user_data["last_name"],
    )

    try:

        user = User.objects.create_user(
            phone=cleaned_phone,
            password=temp_password,
            first_name=user_data["first_name"],
            middle_name=user_data.get("middle_name", ""),
            last_name=user_data["last_name"],
            email=email,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            username=username,
        )

        # send credentials email AFTER successful commit
        if email:
            subject = "Your admin account credentials"

            context = {
                "first_name": user.first_name,
                "phone": user.phone,
                "username": user.username,
                "password": temp_password,
                "app_name": getattr(settings, "APP_NAME", "MyApp"),
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

    except IntegrityError:
        # mostly username DB unique collision
        raise serializers.ValidationError({"user": {"username": ["Username already exists. Try again."]}})

    # 2) SCHOOL (code unique)
    if School.objects.filter(code=school_data["code"]).exists():
        raise serializers.ValidationError({"school": {"code": ["School code already exists."]}})

    try:
        school = School.objects.create(
            owner=user,
            code=school_data["code"],
            name=school_data["name"],
            address=school_data.get("address", ""),
            phone=school_data.get("phone", ""),
            email=(school_data.get("email") or "").strip(),
            logo_file_id=school_data.get("logo_file") or None,
            pan_number=school_data.get("pan_number", ""),
            registration_number=school_data.get("registration_number", ""),
            pan_document_file_id=school_data.get("pan_document_file") or None,
            registration_document_file_id=school_data.get("registration_document_file") or None,
        )
    except DjangoValidationError as e:
        raise serializers.ValidationError({"school": e.message_dict if hasattr(e, "message_dict") else e.messages})
    except IntegrityError:
        raise serializers.ValidationError({"school": {"code": ["School code already exists."]}})

    # 3) PROFILE
    if "date_of_birth_in_ad" not in profile_data or "date_of_birth_in_bs" not in profile_data:
        raise serializers.ValidationError({"profile": {"date_of_birth": ["DOB conversion failed."]}})

    try:
        profile = Profile.objects.create(
            school=school,
            user=user,
            date_of_birth_in_ad=profile_data["date_of_birth_in_ad"],
            date_of_birth_in_bs=profile_data["date_of_birth_in_bs"],
            gender=profile_data.get("gender", ""),
            blood_group=profile_data["blood_group"],
            nationality=profile_data["nationality"],
            religion=profile_data["religion"],
            mother_tongue=profile_data["mother_tongue"],
            citizenship_no=profile_data["citizenship_no"],
            pan_no=profile_data["pan_no"],
        )
    except IntegrityError:
        raise serializers.ValidationError({"profile": {"non_field_errors": ["Profile already exists."]}})

    # 4) ADDRESSES
    # enforce at least one primary
    if not any(bool(a.get("is_primary")) for a in addresses_data):
        for a in addresses_data:
            if a.get("address_type") == AddressType.PERMANENT:
                a["is_primary"] = True

    address_ids: Dict[str, str] = {}
    for idx, addr in enumerate(addresses_data):
        try:
            obj = Address.objects.create(
                profile=profile,
                address_type=addr["address_type"],
                country=addr.get("country", ""),
                province=addr["province"],
                district=addr["district"],
                municipality=addr["municipality"],
                ward_no=addr["ward_no"],
                street=addr.get("street", ""),
                tole=addr.get("tole", ""),
                house_no=addr.get("house_no", ""),
                postal_code=addr.get("postal_code", ""),
                is_primary=addr.get("is_primary", False),
            )
        except IntegrityError:
            raise serializers.ValidationError({"addresses": {idx: {"address_type": ["Duplicate address_type."]}}})

        address_ids[obj.address_type] = str(obj.id)

    # 5) DOCUMENTS
    document_ids: Dict[str, str] = {}

    for key, dtype in REQUIRED_DOC_MAP.items():
        item = documents_data.get(key)
        if not item:
            raise serializers.ValidationError({"documents": {key: ["This document is required."]}})

        remarks = (item.get("remarks") or "").strip() or f"Auto uploaded during onboarding: {dtype}"

        doc_kwargs: Dict[str, Any] = {
            "profile": profile,
            "document_type": dtype,
            "file_id": item["file"],
            "remarks": remarks,
        }
        if (item.get("issued_by") or "").strip():
            doc_kwargs["issued_by"] = item["issued_by"].strip()
        if item.get("issued_date"):
            doc_kwargs["issued_date"] = item["issued_date"]
        if item.get("expiry_date"):
            doc_kwargs["expiry_date"] = item["expiry_date"]

        obj = ProfileDocument.objects.create(**doc_kwargs)
        document_ids[key] = str(obj.id)

    result = OnboardingCreateResult(
        user_id=str(user.id),
        school_id=str(school.id),
        profile_id=str(profile.id),
        address_ids={
            "permanent": address_ids.get(AddressType.PERMANENT, ""),
            "temporary": address_ids.get(AddressType.TEMPORARY, ""),
        },
        document_ids=document_ids,
        username=user.username,
    )

    return {
        "user_id": result.user_id,
        "school_id": result.school_id,
        "profile_id": result.profile_id,
        "address_ids": result.address_ids,
        "document_ids": result.document_ids,
        "username": result.username,
    }


# -----------------------
# READ bundle (by user)
# -----------------------

def fetch_onboarding_bundle_by_user(
    *,
    user_id: str,
    request,
    allow_incomplete: bool = True,
    include_deleted: bool = False,  # ✅ NEW
) -> Dict[str, Any]:
    # ✅ user may be deleted only when include_deleted=True
    user = _get_admin_user_or_404(user_id=user_id, include_deleted=include_deleted)

    # ✅ School might be soft deletable in your system; if you have School.all_objects use it.
    school_manager = getattr(School, "all_objects", None) if include_deleted else School.objects
    if school_manager is None:
        # fallback if School has no all_objects
        school_manager = School.objects

    # ✅ select_related file FKs
    school = (
        school_manager
        .select_related("logo_file", "pan_document_file", "registration_document_file")
        .filter(owner=user)
        .order_by("-created_at")
        .first()
    )

    # ✅ no school -> return incomplete but still stable shape
    if not school:
        if not allow_incomplete:
            raise serializers.ValidationError(
                {"school": {"non_field_errors": ["School not found for this admin user."]}}
            )
        return {
            "user": {
                "id": str(user.id),
                "first_name": user.first_name,
                "middle_name": getattr(user, "middle_name", ""),
                "last_name": user.last_name,
                "phone": user.phone,
                "email": user.email,
                "username": user.username,
                "role": user.role,
                "status": user.status,
            },
            "school": None,
            "profile": None,
            "addresses": [],
            "documents": {k: None for k in REQUIRED_DOC_MAP.keys()},
        }

    # ✅ Profile might also be soft deletable; same pattern
    profile_manager = getattr(Profile, "all_objects", None) if include_deleted else Profile.objects
    if profile_manager is None:
        profile_manager = Profile.objects

    profile = (
        profile_manager
        .filter(school=school, user=user)
        .prefetch_related("addresses")
        .first()
    )

    if not profile and not allow_incomplete:
        raise serializers.ValidationError(
            {"profile": {"non_field_errors": ["Profile not found for school owner."]}}
        )

    addresses = []
    docs_by_type: Dict[str, Any] = {}

    if profile:
        # Address might be soft deletable; if not, Address.objects is fine.
        address_manager = getattr(Address, "all_objects", None) if include_deleted else Address.objects
        if address_manager is None:
            address_manager = Address.objects

        addresses = list(
            address_manager.filter(profile=profile).values(
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
            )
        )

        # Documents might be soft deletable too
        doc_manager = getattr(ProfileDocument, "all_objects", None) if include_deleted else ProfileDocument.objects
        if doc_manager is None:
            doc_manager = ProfileDocument.objects

        docs_qs = (
            doc_manager
            .select_related("file")
            .filter(profile=profile)
            .order_by("-created_at")
        )

        for key, dtype in REQUIRED_DOC_MAP.items():
            doc = docs_qs.filter(document_type=dtype).first()
            docs_by_type[key] = None if not doc else {
                "id": str(doc.id),
                "document_type": doc.document_type,
                "file": _serialize_uploaded_file(doc.file, request=request),
                "remarks": doc.remarks,
                "issued_by": doc.issued_by,
                "issued_date": doc.issued_date.isoformat() if doc.issued_date else None,
                "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                "created_at": doc.created_at.isoformat() if getattr(doc, "created_at", None) else None,
            }

        profile_data = {
            "id": str(profile.id),
            "date_of_birth_in_ad": profile.date_of_birth_in_ad.isoformat() if profile.date_of_birth_in_ad else None,
            "date_of_birth_in_bs": profile.date_of_birth_in_bs,
            "gender": profile.gender,
            "blood_group": profile.blood_group,
            "nationality": profile.nationality,
            "religion": profile.religion,
            "mother_tongue": profile.mother_tongue,
            "citizenship_no": profile.citizenship_no,
            "pan_no": profile.pan_no,
        }
    else:
        profile_data = None
        docs_by_type = {k: None for k in REQUIRED_DOC_MAP.keys()}

    return {
        "user": {
            "id": str(user.id),
            "first_name": user.first_name,
            "middle_name": getattr(user, "middle_name", ""),
            "last_name": user.last_name,
            "phone": user.phone,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "status": user.status,
        },
        "school": {
            "id": str(school.id),
            "code": school.code,
            "name": school.name,
            "address": school.address,
            "phone": school.phone,
            "email": school.email,

            # ✅ expanded file objects
            "logo_file": _serialize_uploaded_file(school.logo_file, request=request),
            "pan_document_file": _serialize_uploaded_file(school.pan_document_file, request=request),
            "registration_document_file": _serialize_uploaded_file(school.registration_document_file, request=request),

            "pan_number": school.pan_number,
            "registration_number": school.registration_number,
            "is_active": school.is_active,
        },
        "profile": profile_data,
        "addresses": addresses,
        "documents": docs_by_type,
    }


# -----------------------
# UPDATE bundle (by user)
# -----------------------

@transaction.atomic
def update_onboarding_bundle_by_user(
    *,
    user_id: str,
    request,
    validated_data: Dict[str, Any],
    partial: bool,
) -> Dict[str, Any]:
    user = _get_admin_user_or_404(user_id=user_id)
    school = _get_school_for_owner_or_error(owner=user)

    profile = Profile.objects.filter(school=school, user=user).first()
    if not profile:
        raise serializers.ValidationError({"profile": {"non_field_errors": ["Profile not found for school owner."]}})

    # 1) USER updates
    user_data = validated_data.get("user") or {}
    if user_data:
        if "email" in user_data:
            email = (user_data.get("email") or "").strip().lower()
            if email and User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                raise serializers.ValidationError({"user": {"email": ["Email already exists."]}})
            user.email = email

        if "phone" in user_data:
            phone = user_data["phone"]  # cleaned by serializer
            if User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
                raise serializers.ValidationError({"user": {"phone": ["Phone already exists."]}})
            user.phone = phone

        for f in ["first_name", "middle_name", "last_name"]:
            if f in user_data:
                setattr(user, f, user_data[f])

        user.save()

    # 2) SCHOOL updates
    school_data = validated_data.get("school") or {}
    if school_data:
        if "code" in school_data:
            code = school_data["code"]
            if School.objects.filter(code=code).exclude(pk=school.pk).exists():
                raise serializers.ValidationError({"school": {"code": ["School code already exists."]}})
            school.code = code

        for f in ["name", "address", "phone", "email", "pan_number", "registration_number"]:
            if f in school_data:
                setattr(school, f, school_data[f])

        if "logo_file" in school_data:
            school.logo_file_id = school_data["logo_file"]
        if "pan_document_file" in school_data:
            school.pan_document_file_id = school_data["pan_document_file"]
        if "registration_document_file" in school_data:
            school.registration_document_file_id = school_data["registration_document_file"]

        try:
            school.save()
        except DjangoValidationError as e:
            raise serializers.ValidationError({"school": e.message_dict if hasattr(e, "message_dict") else e.messages})

    # 3) PROFILE updates
    profile_data = validated_data.get("profile") or {}
    if profile_data:
        if "date_of_birth_in_ad" in profile_data:
            profile.date_of_birth_in_ad = profile_data["date_of_birth_in_ad"]
        if "date_of_birth_in_bs" in profile_data:
            profile.date_of_birth_in_bs = profile_data["date_of_birth_in_bs"]

        for f in ["gender", "blood_group", "nationality", "religion", "mother_tongue", "citizenship_no", "pan_no"]:
            if f in profile_data:
                setattr(profile, f, profile_data[f])

        profile.save()

    # 4) ADDRESSES upsert by address_type
    addresses_data = validated_data.get("addresses")
    if addresses_data is not None:
        for idx, addr in enumerate(addresses_data):
            at = addr.get("address_type")
            if not at:
                raise serializers.ValidationError({"addresses": {idx: {"address_type": ["This field is required."]}}})

            obj, _created = Address.objects.get_or_create(profile=profile, address_type=at)

            for f in [
                "country", "province", "district", "municipality", "ward_no", "street", "tole",
                "house_no", "postal_code", "is_primary"
            ]:
                if f in addr:
                    setattr(obj, f, addr[f])

            if not partial:
                for req in ["province", "district", "municipality", "ward_no"]:
                    if not getattr(obj, req):
                        raise serializers.ValidationError({"addresses": {idx: {req: ["This field is required."]}}})

            obj.save()

        if not partial:
            have = set(Address.objects.filter(profile=profile).values_list("address_type", flat=True))
            need = {AddressType.PERMANENT, AddressType.TEMPORARY}
            if need - have:
                raise serializers.ValidationError({"addresses": ["Permanent and temporary addresses must exist."]})

    # 5) DOCUMENTS update latest per type
    docs_data = validated_data.get("documents") or {}
    if docs_data:
        for key, dtype in REQUIRED_DOC_MAP.items():
            if key not in docs_data:
                continue

            item = docs_data[key]
            existing = ProfileDocument.objects.filter(profile=profile, document_type=dtype).order_by("-created_at").first()

            file_id = item.get("file")
            if not existing and not file_id:
                raise serializers.ValidationError({"documents": {key: {"file": ["This field is required."]}}})

            remarks = (item.get("remarks") or "").strip() or f"Auto uploaded during onboarding: {dtype}"

            if existing:
                if file_id:
                    existing.file_id = file_id
                if "remarks" in item:
                    existing.remarks = remarks
                if "issued_by" in item:
                    existing.issued_by = (item.get("issued_by") or "").strip()
                if "issued_date" in item:
                    existing.issued_date = item.get("issued_date")
                if "expiry_date" in item:
                    existing.expiry_date = item.get("expiry_date")
                existing.save()
            else:
                ProfileDocument.objects.create(
                    profile=profile,
                    document_type=dtype,
                    file_id=file_id,
                    remarks=remarks,
                    issued_by=(item.get("issued_by") or "").strip(),
                    issued_date=item.get("issued_date"),
                    expiry_date=item.get("expiry_date"),
                )

    if not partial:
        missing = []
        for key, dtype in REQUIRED_DOC_MAP.items():
            if not ProfileDocument.objects.filter(profile=profile, document_type=dtype).exists():
                missing.append(key)
        if missing:
            raise serializers.ValidationError({"documents": {k: ["Missing required document."] for k in missing}})

    return fetch_onboarding_bundle_by_user(
        user_id=str(user.id),
        request=request,
        allow_incomplete=True,
    )


@transaction.atomic
def delete_onboarding_bundle_by_user(*, user_id: str) -> None:
    user = _get_admin_user_or_404(user_id=user_id)

    # Deactivate school
    school = School.objects.filter(owner=user).order_by("-created_at").first()
    if school:
        school.is_active = False
        school.save(update_fields=["is_active"])

        # optional but recommended
        if hasattr(school, "settings") and school.settings_id:
            school.settings.is_active = False
            school.settings.save(update_fields=["is_active"])

    # Deactivate + mark user deleted
    user.status = UserStatus.DELETED
    user.is_active = False
    user.save(update_fields=["status", "is_active"])

    # Soft delete (sets is_deleted / deleted_at)
    user.soft_delete()
