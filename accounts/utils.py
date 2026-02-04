# accounts/utils.py
import random
import re
import hmac
import hashlib
from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


OTP_LENGTH = 6


def generate_numeric_otp(length: int = OTP_LENGTH) -> str:
    # 6-digit numeric OTP
    start = 10 ** (length - 1)
    end = (10 ** length) - 1
    return str(random.randint(start, end))


def hash_otp(otp: str, *, salt: str) -> str:
    """
    Hash OTP using HMAC with SECRET_KEY.
    Salt should be stable per record (e.g., OTP record id or user id + created).
    """
    key = settings.SECRET_KEY.encode("utf-8")
    msg = f"{salt}:{otp}".encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return digest


def verify_otp(otp: str, otp_hash: str, *, salt: str) -> bool:
    candidate = hash_otp(otp, salt=salt)
    return constant_time_compare(candidate, otp_hash)


def validate_strong_password(password: str, *, user=None) -> None:
    """
    Enforces:
    - min 8
    - 1 uppercase
    - 1 lowercase
    - 1 number
    - 1 symbol
    Also runs Django's AUTH_PASSWORD_VALIDATORS via validate_password.
    """
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")

    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least 1 uppercase letter.")

    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least 1 lowercase letter.")

    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least 1 number.")

    # symbol: anything not alnum/underscore
    if not re.search(r"[^\w\s]", password):
        raise ValidationError("Password must contain at least 1 symbol (special character).")

    # run Django validators too (common password, similarity, etc.)
    validate_password(password, user=user)
