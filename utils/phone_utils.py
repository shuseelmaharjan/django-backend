# utils/phone_utils.py
import os
from common.constants import COUNTRY_DATA

def get_country_config():
    country = os.environ.get("COUNTRY", "").strip()
    for c in COUNTRY_DATA:
        if c["country"].lower() == country.lower():
            return c
    return None


def normalize_phone_for_login(raw: str) -> str:
    """
    Converts local or international phone to normalized E.164
    based on COUNTRY env.
    """
    raw = raw.strip().replace(" ", "").replace("-", "")

    country = get_country_config()
    if not country:
        return raw  # fallback, don't break login

    dial = country["dial_code"]
    phone_len = country["phone_length"]

    # Already international
    if raw.startswith(dial):
        return raw

    # Local number → attach dial code
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == phone_len:
        return f"{dial}{digits}"

    return raw

def strip_dial_code(phone: str) -> str:
    if not phone:
        return phone

    country = os.environ.get("COUNTRY", "").strip()
    for c in COUNTRY_DATA:
        if c["country"].lower() == country.lower():
            dial = c["dial_code"]
            if phone.startswith(dial):
                return phone[len(dial):]
            break
    return phone
