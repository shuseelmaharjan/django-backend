# utils/username.py
import re
from django.utils.text import slugify

MIN_USERNAME_LEN = 6

def _clean(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "", s)  # remove spaces
    s = slugify(s).replace("-", "")  # ascii-ish, no dashes
    return s

def build_base_username(first_name: str, middle_name: str, last_name: str) -> str:
    """
    Strategy:
      1) first+middle (if middle exists) else first+last else first
      2) ensure >= 6 (pad with 'x')
    """
    f = _clean(first_name)
    m = _clean(middle_name)
    l = _clean(last_name)

    base = ""
    if f and m:
        base = f + m
    elif f and l:
        base = f + l
    else:
        base = f or l or "user"

    if len(base) < MIN_USERNAME_LEN:
        base = (base + "x" * MIN_USERNAME_LEN)[:MIN_USERNAME_LEN]
    return base

def make_unique_username(base: str, exists_fn) -> str:
    """
    exists_fn(username)->bool (e.g., User.objects.filter(username=...).exists())
    Produces base, base123, base1223, etc.
    """
    if not exists_fn(base):
        return base

    # deterministic-ish increments
    i = 1
    while True:
        candidate = f"{base}{100 + i}"
        if not exists_fn(candidate):
            return candidate
        i += 1
