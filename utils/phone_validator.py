# utils/phone_validator.py
from django.core.exceptions import ValidationError
from utils.user_validators import get_country_config


def _strip_separators(s: str) -> str:
    return (s or "").replace(" ", "").replace("-", "").strip()


def _digits_only(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _strip_dial_code(raw: str, dial_code: str) -> tuple[str, bool]:
    """
    Returns (national_number, had_dial_code)
    Accept dial_code like '+977' and also '977'.
    """
    clean = _strip_separators(raw)

    dc_digits = _digits_only(dial_code)  # '977'
    # If starts with +<dc> or <dc>
    if clean.startswith(dial_code):
        return clean[len(dial_code):], True

    if clean.startswith("+") and _digits_only(clean).startswith(dc_digits):
        # handle cases like '+977981...' even if dial_code stored as '+977'
        # remove leading '+' then remove dc_digits from digits stream
        digits = _digits_only(clean)
        national = digits[len(dc_digits):]
        return national, True

    if clean.startswith(dc_digits):
        # handle '977981...' (without +)
        return clean[len(dc_digits):], True

    # Has some other + dial code
    if clean.startswith("+"):
        raise ValidationError(f"Invalid dial code. Expected {dial_code} for {get_country_config().get('country')}")

    return clean, False


def validate_phone_number(phone_number: str, country_config=None) -> tuple[bool, str | None]:
    """
    Validate against dynamic config.

    Supports:
      - phone numbers: must start with phone-startswith and length = phone_length
      - tel numbers:
          a) with prefix in tel-startswith: length must be len(prefix)+tel_length
          b) without prefix: length must be tel_length (we will add prefix in formatting)
    """
    if not phone_number:
        return True, None

    if country_config is None:
        country_config = get_country_config()

    dial_code = country_config["dial_code"]
    phone_length = int(country_config["phone_length"])
    tel_length = int(country_config["tel_length"])

    phone_starts = tuple(country_config.get("phone-startswith", []))
    tel_starts = tuple(country_config.get("tel-startswith", []))

    national, _had_dc = _strip_dial_code(phone_number, dial_code)
    national = _strip_separators(national)

    if not _digits_only(national).isdigit():
        return False, "Phone number must contain only digits"

    national_digits = _digits_only(national)

    # ---- PHONE (mobile)
    if national_digits.startswith(phone_starts):
        if len(national_digits) != phone_length:
            return False, f"Mobile number must be {phone_length} digits for {country_config['country']}"
        return True, None

    # ---- TEL (with prefix)
    for pfx in tel_starts:
        pfx_digits = _digits_only(pfx)
        if national_digits.startswith(pfx_digits):
            rest = national_digits[len(pfx_digits):]
            if len(rest) != tel_length:
                return False, (
                    f"Telephone number must be '{pfx}' + {tel_length} digits "
                    f"for {country_config['country']}"
                )
            return True, None

    # ---- TEL (without prefix)
    # Example Nepal: 5555139 (7 digits) should be valid and formatted as +97701xxxxxxx
    if len(national_digits) == tel_length and tel_starts:
        return True, None

    # Otherwise invalid
    expected_tel_examples = []
    if tel_starts:
        expected_tel_examples.append(f"{tel_starts[0]} + {tel_length} digits")
        expected_tel_examples.append(f"{tel_length} digits (local tel)")
    expected_phone_examples = []
    if phone_starts:
        expected_phone_examples.append(f"starts with {list(phone_starts)} and {phone_length} digits")

    return False, (
        f"Invalid number for {country_config['country']}. "
        f"Expected mobile ({'; '.join(expected_phone_examples)}) or tel ({'; '.join(expected_tel_examples)})."
    )


def format_phone_number(phone_number: str, country_config=None) -> str:
    """
    Format output:
      - Always returns with dial_code (like +977) + national formatted
      - If tel provided as local (tel_length digits), we add first tel-startswith prefix.
    """
    if not phone_number:
        return phone_number

    if country_config is None:
        country_config = get_country_config()

    dial_code = country_config["dial_code"]
    tel_length = int(country_config["tel_length"])
    tel_starts = tuple(country_config.get("tel-startswith", []))

    national, _had_dc = _strip_dial_code(phone_number, dial_code)
    national_digits = _digits_only(national)

    # If it is local tel (exact tel_length), prepend first tel prefix
    if tel_starts and len(national_digits) == tel_length:
        pfx_digits = _digits_only(tel_starts[0])
        national_digits = f"{pfx_digits}{national_digits}"

    # Ensure dial code has '+'
    if not dial_code.startswith("+"):
        dial_code = f"+{dial_code}"

    return f"{dial_code}{national_digits}"


def clean_and_validate_phone(phone_number: str) -> str:
    """
    Full validation + formatting.
    Raises django.core.exceptions.ValidationError on invalid.
    Returns formatted number.
    """
    if not phone_number:
        return phone_number

    country_config = get_country_config()

    is_valid, error_message = validate_phone_number(phone_number, country_config)
    if not is_valid:
        raise ValidationError(error_message)

    return format_phone_number(phone_number, country_config)
