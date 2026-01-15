"""
Centralized user field validators for username, email, and phone.
These validators check uniqueness and format, and can be reused across serializers.
"""
from rest_framework import serializers
from django.conf import settings
from common.constants import COUNTRY_DATA


def get_country_config():
    """
    Get country configuration from settings.COUNTRY.
    Accepts country_code (e.g., "NP") or country name (e.g., "Nepal").
    Returns the matching country dict from COUNTRY_DATA.
    """
    selected = (getattr(settings, "COUNTRY", "") or "").strip()

    if not selected:
        return COUNTRY_DATA[0]

    # Try matching by country_code first
    for row in COUNTRY_DATA:
        if row["country_code"].lower() == selected.lower():
            return row

    # Then try matching by country name
    for row in COUNTRY_DATA:
        if row["country"].lower() == selected.lower():
            return row

    # Default to first entry if not found
    return COUNTRY_DATA[0]


def validate_username_unique(username, exclude_user_id=None):
    """
    Validate that username is unique (case-insensitive).

    Args:
        username: The username to validate
        exclude_user_id: Optional user ID to exclude from uniqueness check (for updates)

    Returns:
        str: The cleaned username

    Raises:
        serializers.ValidationError: If username already exists
    """
    from accounts.models import User

    v = (username or "").strip()

    # Allow blank username if your model allows it
    if v == "":
        return v

    qs = User.objects.filter(username__iexact=v)
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)

    if qs.exists():
        raise serializers.ValidationError("Username already exists.")

    return v


def validate_email_unique(email, exclude_user_id=None):
    """
    Validate that email is unique (case-insensitive).

    Args:
        email: The email to validate
        exclude_user_id: Optional user ID to exclude from uniqueness check (for updates)

    Returns:
        str: The cleaned and normalized email (lowercase)

    Raises:
        serializers.ValidationError: If email already exists
    """
    from accounts.models import User

    v = (email or "").strip().lower()

    qs = User.objects.filter(email__iexact=v)
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)

    if qs.exists():
        raise serializers.ValidationError("Email already exists.")

    return v


def normalize_and_validate_phone(phone, exclude_user_id=None, allow_blank=True):
    """
    Normalize phone number with country dial code and validate format and uniqueness.

    Normalizes to: <dial_code><national_number>
    Example: +9779812345678

    Rules:
    - If input has +, it must match dial_code for configured country
    - National part must be digits only
    - National length must equal phone_length for configured country
    - If input has no dial_code, server adds it

    Args:
        phone: The phone number to validate
        exclude_user_id: Optional user ID to exclude from uniqueness check (for updates)
        allow_blank: Whether to allow blank/empty phone numbers

    Returns:
        str: The normalized phone number with dial code

    Raises:
        serializers.ValidationError: If phone is invalid or already exists
    """
    from accounts.models import User

    cfg = get_country_config()
    dial_code = cfg["dial_code"]
    phone_len = int(cfg["phone_length"])

    v = (phone or "").strip()

    # Handle blank phone
    if v == "":
        if allow_blank:
            return ""
        else:
            raise serializers.ValidationError("Phone number is required.")

    # Remove spaces, hyphens, parentheses, dots
    compact = "".join(ch for ch in v if ch not in [" ", "-", "(", ")", "."])

    # Handle dial code
    if compact.startswith("+"):
        if not compact.startswith(dial_code):
            raise serializers.ValidationError(
                f"Phone must start with {dial_code} for {cfg['country']}."
            )
        national = compact[len(dial_code):]
    else:
        national = compact

    # Validate national number format
    if not national.isdigit():
        raise serializers.ValidationError("Phone must contain digits only (excluding dial code).")

    if len(national) != phone_len:
        raise serializers.ValidationError(
            f"Phone must be exactly {phone_len} digits for {cfg['country']}."
        )

    normalized = f"{dial_code}{national}"

    # Check uniqueness
    qs = User.objects.filter(phone=normalized)
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)

    if qs.exists():
        raise serializers.ValidationError("Phone number already exists.")

    return normalized


def clean_phone_input(phone):
    """
    Clean phone input by removing common formatting characters.
    Does not validate or normalize - just cleans.

    Args:
        phone: Raw phone input

    Returns:
        str: Cleaned phone number
    """
    v = (phone or "").strip()
    if v == "":
        return ""

    # Remove spaces, hyphens, parentheses, dots
    return "".join(ch for ch in v if ch not in [" ", "-", "(", ")", "."])

