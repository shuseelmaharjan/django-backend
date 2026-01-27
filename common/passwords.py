import secrets
import string

def generate_strong_password(length: int = 14) -> str:
    """
    Strong random password:
    - letters + digits
    - guaranteed at least 1 lowercase, 1 uppercase, 1 digit
    """
    if length < 12:
        length = 12

    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    alphabet = lower + upper + digits

    # guarantee variety
    pwd = [
        secrets.choice(lower),
        secrets.choice(upper),
        secrets.choice(digits),
    ]
    pwd += [secrets.choice(alphabet) for _ in range(length - len(pwd))]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)
