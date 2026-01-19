# accounts/services/admin_onboarding.py
import secrets
import string
import datetime
from typing import Any

from django.db import transaction

from accounts.models import User
from common.constants import UserRole, UserStatus
from schools.models import School
from profiles.models import Profile, Address, ProfileDocument

import nepali_datetime


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@transaction.atomic
def create_admin_user(
    *,
    phone: str,
    email: str = "",
    first_name: str = "",
    middle_name: str = "",
    last_name: str = "",
) -> User:
    if email and User.objects.filter(email__iexact=email).exists():
        raise ValueError("Email already exists")

    password = generate_temp_password()
    user = User.objects.create_user(
        phone=phone,
        password=password,
        email=email or "",
        first_name=first_name or "",
        middle_name=middle_name or "",
        last_name=last_name or "",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        is_staff=True,
    )
    user._temp_password = password
    return user


@transaction.atomic
def create_school_for_admin(*, owner: User, code: str, name: str, **kwargs) -> School:
    school = School.objects.create(
        owner=owner,
        code=code,
        name=name,
        address=kwargs.get("address", ""),
        phone=kwargs.get("phone", ""),
        email=kwargs.get("email", ""),
        logo_file=kwargs.get("logo_file"),
        pan_number=kwargs.get("pan_number", ""),
        registration_number=kwargs.get("registration_number", ""),
        pan_document_file=kwargs.get("pan_document_file"),
        registration_document_file=kwargs.get("registration_document_file"),
        user_photo=kwargs.get("user_photo"),
        citizenship_front=kwargs.get("citizenship_front"),
        citizenship_back=kwargs.get("citizenship_back"),
        is_active=kwargs.get("is_active", True),
    )
    return school


# -----------------------------
# DOB normalize to AD
# -----------------------------
def bs_to_ad_date(bs_date_str: str) -> datetime.date:
    y, m, d = map(int, bs_date_str.split("-"))
    bs = nepali_datetime.date(y, m, d)
    return bs.to_datetime_date()


def normalize_dob_to_ad(date_of_birth: Any, dob_type: str = "ad") -> datetime.date | None:
    if not date_of_birth:
        return None

    if isinstance(date_of_birth, datetime.date):
        return date_of_birth

    if isinstance(date_of_birth, str):
        raw = date_of_birth.strip()
        if not raw:
            return None
        if dob_type == "bs":
            return bs_to_ad_date(raw)
        return datetime.datetime.strptime(raw, "%Y-%m-%d").date()

    raise ValueError("Unsupported date_of_birth type")


@transaction.atomic
def create_profile_bundle(
    *,
    user: User,
    school: School,
    profile_data: dict,
    addresses_data: list[dict],
    documents_data: list[dict],
    date_of_birth_type: str = "ad",
    replace_documents: bool = False,
) -> Profile:
    # normalize DOB into AD
    if "date_of_birth" in profile_data:
        profile_data["date_of_birth"] = normalize_dob_to_ad(
            profile_data.get("date_of_birth"),
            dob_type=date_of_birth_type,
        )

    profile, _ = Profile.objects.get_or_create(
        user=user,
        school=school,
        defaults=profile_data,
    )

    # upsert profile fields
    for k, v in profile_data.items():
        setattr(profile, k, v)
    profile.save()

    # upsert multiple addresses by (profile, address_type)
    for addr in addresses_data:
        if "address_type" not in addr:
            raise ValueError("Each address must include address_type")

        Address.objects.update_or_create(
            profile=profile,
            address_type=addr["address_type"],
            defaults=addr,
        )

    # enforce single primary (if any primary provided)
    primaries = [a for a in addresses_data if a.get("is_primary")]
    if len(primaries) == 1:
        primary_type = primaries[0]["address_type"]
        Address.objects.filter(profile=profile).exclude(address_type=primary_type).update(is_primary=False)

    # replace docs if asked (useful on PUT)
    if replace_documents:
        ProfileDocument.objects.filter(profile=profile).delete()

    # create documents
    for doc in documents_data:
        if "document_type" not in doc or "file" not in doc:
            raise ValueError("Each document must include document_type and file")

        ProfileDocument.objects.create(
            profile=profile,
            document_type=doc["document_type"],
            file_id=doc["file"],  # expects UUID (UploadedFile id)
            issued_by=doc.get("issued_by", ""),
            issued_date=doc.get("issued_date"),
            expiry_date=doc.get("expiry_date"),
            remarks=doc.get("remarks", ""),
        )

    return profile


def is_profile_complete_for_admin(user: User) -> bool:
    school_qs = School.objects.filter(owner=user)
    if not school_qs.exists():
        return False
    school = school_qs.order_by("-created_at").first()

    profile_qs = Profile.objects.filter(user=user, school=school)
    if not profile_qs.exists():
        return False
    profile = profile_qs.first()

    return profile.addresses.exists() and profile.documents.exists()
