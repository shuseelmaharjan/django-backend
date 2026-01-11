from django.conf import settings
from django.core.exceptions import ValidationError
from common.constants import COUNTRY_DATA


def get_country_config():
    """Get country configuration from environment"""
    country_name = getattr(settings, 'COUNTRY', 'Nepal')

    for country in COUNTRY_DATA:
        if country['country'] == country_name:
            return country

    # Default to Nepal if not found
    return COUNTRY_DATA[0]


def validate_phone_number(phone_number, country_config=None):
    """
    Validate phone number against country-specific rules
    Returns:  tuple (is_valid, error_message)
    """
    if not phone_number:
        return True, None

    if country_config is None:
        country_config = get_country_config()

    # Remove spaces and dashes for validation
    clean_number = phone_number.replace(" ", "").replace("-", "")

    # Check if number has dial code
    dial_code = country_config['dial_code']
    if clean_number.startswith(dial_code):
        # Remove dial code for length validation
        number_without_code = clean_number[len(dial_code):]
    elif clean_number.startswith('+'):
        # Has some dial code but not the expected one
        return False, f"Invalid dial code.  Expected {dial_code} for {country_config['country']}"
    else:
        number_without_code = clean_number

    # Validate length
    phone_length = country_config['phone_length']
    tel_length = country_config['tel_length']

    if len(number_without_code) not in [phone_length, tel_length]:
        return False, (
            f"Phone number must be {phone_length} or {tel_length} digits "
            f"for {country_config['country']}"
        )

    # Check if number contains only digits
    if not number_without_code.isdigit():
        return False, "Phone number must contain only digits"

    return True, None


def format_phone_number(phone_number, country_config=None):
    """
    Format phone number with dial code if not present
    Returns: formatted phone number
    """
    if not phone_number:
        return phone_number

    if country_config is None:
        country_config = get_country_config()

    # Remove spaces and dashes
    clean_number = phone_number.replace(" ", "").replace("-", "")

    # Check if already has dial code
    dial_code = country_config['dial_code']
    if clean_number.startswith(dial_code):
        return clean_number
    elif clean_number.startswith('+'):
        # Already has a dial code, return as is
        return clean_number
    else:
        # Add dial code
        return f"{dial_code}{clean_number}"


def clean_and_validate_phone(phone_number):
    """
    Complete phone validation and formatting
    Raises ValidationError if invalid
    Returns: formatted phone number
    """
    if not phone_number:
        return phone_number

    country_config = get_country_config()

    # First validate
    is_valid, error_message = validate_phone_number(phone_number, country_config)
    if not is_valid:
        raise ValidationError(error_message)

    # Then format
    return format_phone_number(phone_number, country_config)