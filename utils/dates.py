# utils/dates.py
import datetime
import nepali_datetime
from django.core.exceptions import ValidationError

def bs_to_ad(bs_date_str: str) -> datetime.date:
    """
    bs_date_str: 'YYYY-MM-DD' in Nepali (Bikram Sambat)
    """
    try:
        y, m, d = map(int, (bs_date_str or "").split("-"))
        bs = nepali_datetime.date(y, m, d)
        return bs.to_datetime_date()
    except Exception:
        raise ValidationError("Invalid BS date. Use YYYY-MM-DD and ensure valid Nepali date.")

def ad_to_bs(ad_date: datetime.date) -> str:
    """
    returns 'YYYY-MM-DD' in BS
    """
    try:
        bs = nepali_datetime.date.from_datetime_date(ad_date)
        return f"{bs.year:04d}-{bs.month:02d}-{bs.day:02d}"
    except Exception:
        raise ValidationError("Invalid AD date.")
