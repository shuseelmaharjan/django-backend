# utils/email_validator.py
from django.core.exceptions import ValidationError

def validate_unique_email(email: str, user_model, exclude_user_id=None) -> str:
    value = (email or "").strip().lower()
    if not value:
        return value

    qs = user_model.all_objects.filter(email__iexact=value)
    if exclude_user_id:
        qs = qs.exclude(pk=exclude_user_id)

    if qs.exists():
        raise ValidationError("Email already exists.")
    return value
