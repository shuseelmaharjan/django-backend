from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from fees.models import FeePaymentAllocation


# =============================================================================
# Visual constants
# =============================================================================

BLACK = colors.HexColor("#111111")
DARK_GREY = colors.HexColor("#3F3F3F")
MID_GREY = colors.HexColor("#B8B8B8")
LIGHT_GREY = colors.HexColor("#EEEEEE")
WHITE = colors.white

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"
FONT_BOLD_OBLIQUE = "Helvetica-BoldOblique"


# =============================================================================
# Generic helpers
# =============================================================================
def _display_phone(phone: str | None) -> str:
    if not phone:
        return "-"

    phone = str(phone).strip()

    if phone.startswith("+977"):
        return phone[4:]

    if phone.startswith("977"):
        return phone[3:]

    return phone


def _safe_text(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _money(value: Any) -> str:
    return f"{_as_decimal(value):,.2f}"


def _student_name(student) -> str:
    parts = [
        getattr(student, "first_name", ""),
        getattr(student, "middle_name", ""),
        getattr(student, "last_name", ""),
    ]
    name = " ".join(str(part).strip() for part in parts if str(part).strip())
    return name or _safe_text(student)


def _student_registration_no(student) -> str:
    return _safe_text(
        getattr(
            student,
            "registration_no",
            getattr(student, "registration_number", None),
        )
    )


def _section_name(enrollment) -> str:
    section = getattr(enrollment, "section", None)
    if section is not None:
        return _safe_text(getattr(section, "name", section))
    return _safe_text(getattr(enrollment, "section_name", None))


def _display_user_name(user) -> str:
    if not user:
        return "-"

    getter = getattr(user, "get_full_name", None)
    if callable(getter):
        full_name = getter().strip()
        if full_name:
            return full_name

    first_name = getattr(user, "first_name", "")
    last_name = getattr(user, "last_name", "")
    joined = " ".join(x.strip() for x in [first_name, last_name] if x and x.strip())
    if joined:
        return joined

    return _safe_text(user)


def _school_registration_no(school) -> str:
    return _safe_text(
        getattr(
            school,
            "registration_number",
            getattr(school, "registration_no", None),
        )
    )


def _school_pan(school) -> str:
    return _safe_text(getattr(school, "pan_number", None))


def _school_address(school) -> str:
    return _safe_text(getattr(school, "address", None))


def _school_phone(school) -> str:
    return _display_phone(getattr(school, "phone", None))


def _school_email(school) -> str:
    return _safe_text(getattr(school, "email", None))


# =============================================================================
# Logo helpers
# =============================================================================


def _read_file_value(file_value: Any) -> bytes | str | None:
    """
    Resolve a school logo into a ReportLab-compatible source.

    This supports:
    - local Django ImageField/FileField values,
    - remote-storage FieldFile values (S3/MinIO/etc.),
    - relative paths stored in the database,
    - MEDIA_URL URLs,
    - absolute HTTP(S) logo URLs,
    - file-handler wrapper objects exposing file/image/document/path/url.

    Returning bytes instead of only a filesystem path fixes the common case
    where ``FieldFile.path`` is unavailable because the project uses remote
    storage or a custom file-handler app.
    """

    if not file_value:
        return None

    # Django FieldFile/ImageFieldFile: local storage first.
    try:
        path = file_value.path
        if path and Path(path).is_file():
            return str(path)
    except (AttributeError, NotImplementedError, ValueError, OSError):
        pass

    # Django FieldFile/ImageFieldFile: works with local and remote storage.
    try:
        file_value.open("rb")
        payload = file_value.read()
        try:
            file_value.close()
        except Exception:
            pass
        if payload:
            return bytes(payload)
    except Exception:
        pass

    # Custom file-handler objects often wrap the real file in one of these.
    for nested_name in (
        "file",
        "image",
        "document",
        "attachment",
        "upload",
        "logo",
    ):
        nested = getattr(file_value, nested_name, None)
        if nested is not None and nested is not file_value:
            resolved = _read_file_value(nested)
            if resolved:
                return resolved

    raw = str(file_value).strip()
    if not raw:
        return None

    # Direct local path.
    direct = Path(raw)
    if direct.is_file():
        return str(direct)

    media_root = getattr(settings, "MEDIA_ROOT", None)
    media_url = str(getattr(settings, "MEDIA_URL", "/media/") or "/media/")

    parsed = urlparse(raw)
    storage_name = raw

    if parsed.scheme in ("http", "https"):
        url_path = unquote(parsed.path)
        media_prefix = urlparse(media_url).path or media_url

        if media_prefix and url_path.startswith(media_prefix):
            storage_name = url_path[len(media_prefix):].lstrip("/")
        else:
            # Absolute remote URL fallback. Use a short timeout so a broken
            # remote logo never blocks financial document generation.
            try:
                request = Request(raw, headers={"User-Agent": "SchoolERP-PDF/1.0"})
                with urlopen(request, timeout=5) as response:
                    payload = response.read()
                return payload or None
            except Exception:
                return None
    elif raw.startswith(media_url):
        storage_name = raw[len(media_url):].lstrip("/")
    else:
        storage_name = raw.lstrip("/")

    # MEDIA_ROOT path.
    if media_root:
        media_path = Path(media_root) / storage_name
        if media_path.is_file():
            return str(media_path)

    # Configured Django storage (local, S3, MinIO, etc.).
    try:
        if default_storage.exists(storage_name):
            with default_storage.open(storage_name, "rb") as stored_file:
                payload = stored_file.read()
            if payload:
                return bytes(payload)
    except Exception:
        pass

    return None


def _school_logo_source(school) -> bytes | str | None:
    """Find the school logo without assuming one exact model schema."""

    direct_names = (
        "logo",
        "school_logo",
        "logo_image",
        "logo_file",
        "logo_url",
        "emblem",
        "image",
        "profile_picture",
    )

    for field_name in direct_names:
        resolved = _read_file_value(getattr(school, field_name, None))
        if resolved:
            return resolved

    # Inspect concrete model fields whose names clearly describe a logo/image.
    model_meta = getattr(school, "_meta", None)
    if model_meta is not None:
        for model_field in model_meta.get_fields():
            field_name = getattr(model_field, "name", "")
            lowered = field_name.lower()
            if any(token in lowered for token in ("logo", "emblem", "badge")):
                resolved = _read_file_value(getattr(school, field_name, None))
                if resolved:
                    return resolved

    # Some projects keep branding in a related one-to-one model.
    for relation_name in (
        "branding",
        "brand",
        "school_branding",
        "profile",
        "settings",
    ):
        try:
            related = getattr(school, relation_name, None)
        except Exception:
            related = None
        if related is None:
            continue

        for field_name in direct_names:
            resolved = _read_file_value(getattr(related, field_name, None))
            if resolved:
                return resolved

    return None


def _to_image_reader(source: bytes | str | None) -> ImageReader | None:
    if not source:
        return None
    try:
        if isinstance(source, (bytes, bytearray, memoryview)):
            return ImageReader(BytesIO(bytes(source)))
        return ImageReader(source)
    except Exception:
        return None

def _draw_image_contain(
    c: canvas.Canvas,
    path: bytes | str | None,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    preserve_aspect_ratio: bool = True,
) -> None:
    if not path:
        return

    try:
        image = _to_image_reader(path)
        if image is None:
            return
        image_width, image_height = image.getSize()

        if preserve_aspect_ratio and image_width and image_height:
            scale = min(width / image_width, height / image_height)
            draw_width = image_width * scale
            draw_height = image_height * scale
            draw_x = x + (width - draw_width) / 2
            draw_y = y + (height - draw_height) / 2
        else:
            draw_x, draw_y = x, y
            draw_width, draw_height = width, height

        c.drawImage(
            image,
            draw_x,
            draw_y,
            width=draw_width,
            height=draw_height,
            mask="auto",
            preserveAspectRatio=preserve_aspect_ratio,
        )
    except Exception:
        # A broken logo must never stop financial PDF generation.
        return


def _draw_logo_watermark(
    c: canvas.Canvas,
    logo_path: bytes | str | None,
    center_x: float,
    center_y: float,
    size: float,
    alpha: float = 0.07,
) -> None:
    if not logo_path:
        return

    c.saveState()
    try:
        c.setFillAlpha(alpha)
        c.setStrokeAlpha(alpha)
    except Exception:
        pass

    _draw_image_contain(
        c,
        logo_path,
        center_x - size / 2,
        center_y - size / 2,
        size,
        size,
    )
    c.restoreState()


# =============================================================================
# Text drawing helpers
# =============================================================================


def _fit_font_size(
    text: str,
    max_width: float,
    preferred_size: float,
    *,
    font_name: str = FONT_REGULAR,
    minimum_size: float = 7,
) -> float:
    size = preferred_size
    while size > minimum_size and stringWidth(text, font_name, size) > max_width:
        size -= 0.25
    return size


def _draw_centered(
    c: canvas.Canvas,
    text: str,
    center_x: float,
    y: float,
    *,
    font_name: str = FONT_REGULAR,
    font_size: float = 12,
    max_width: float | None = None,
) -> None:
    text = _safe_text(text)
    size = (
        _fit_font_size(text, max_width, font_size, font_name=font_name)
        if max_width
        else font_size
    )
    c.setFont(font_name, size)
    c.setFillColor(BLACK)
    c.drawCentredString(center_x, y, text)


def _draw_right(
    c: canvas.Canvas,
    text: str,
    right_x: float,
    y: float,
    *,
    font_name: str = FONT_REGULAR,
    font_size: float = 12,
    max_width: float | None = None,
) -> None:
    text = _safe_text(text)
    size = (
        _fit_font_size(text, max_width, font_size, font_name=font_name)
        if max_width
        else font_size
    )
    c.setFont(font_name, size)
    c.setFillColor(BLACK)
    c.drawRightString(right_x, y, text)


def _draw_label_value(
    c: canvas.Canvas,
    x: float,
    y: float,
    label: str,
    value: Any,
    *,
    label_size: float = 12,
    value_size: float = 12,
    max_width: float | None = None,
) -> None:
    label_text = f"{label}:"
    c.setFont(FONT_BOLD, label_size)
    c.setFillColor(BLACK)
    c.drawString(x, y, label_text)

    value_x = x + stringWidth(label_text, FONT_BOLD, label_size) + 2
    available = max_width - (value_x - x) if max_width else None
    value_text = _safe_text(value)
    size = (
        _fit_font_size(value_text, available, value_size)
        if available and available > 0
        else value_size
    )
    c.setFont(FONT_REGULAR, size)
    c.drawString(value_x, y, value_text)


def _wrap_text(
    text: str,
    max_width: float,
    font_name: str,
    font_size: float,
) -> list[str]:
    words = _safe_text(text, "").split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


# =============================================================================
# Amount in words
# =============================================================================

_ONES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)

_TENS = (
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
)


def _integer_to_words(number: int) -> str:
    if number < 0:
        return f"minus {_integer_to_words(abs(number))}"
    if number < 20:
        return _ONES[number]
    if number < 100:
        tens, remainder = divmod(number, 10)
        return _TENS[tens] if remainder == 0 else f"{_TENS[tens]} {_ONES[remainder]}"
    if number < 1_000:
        hundreds, remainder = divmod(number, 100)
        result = f"{_ONES[hundreds]} hundred"
        return result if remainder == 0 else f"{result} {_integer_to_words(remainder)}"
    if number < 100_000:
        thousands, remainder = divmod(number, 1_000)
        result = f"{_integer_to_words(thousands)} thousand"
        return result if remainder == 0 else f"{result} {_integer_to_words(remainder)}"
    if number < 10_000_000:
        lakhs, remainder = divmod(number, 100_000)
        result = f"{_integer_to_words(lakhs)} lakh"
        return result if remainder == 0 else f"{result} {_integer_to_words(remainder)}"

    crores, remainder = divmod(number, 10_000_000)
    result = f"{_integer_to_words(crores)} crore"
    return result if remainder == 0 else f"{result} {_integer_to_words(remainder)}"


def _amount_in_words(value: Any) -> str:
    amount = _as_decimal(value).quantize(Decimal("0.01"))
    rupees = int(amount)
    paisa = int((amount - Decimal(rupees)) * 100)

    result = _integer_to_words(rupees)
    if paisa:
        result = f"{result} and {_integer_to_words(paisa)} paisa"

    return f"{result.capitalize()} only."


# =============================================================================
# Nepali month mapping (same business mapping as frontend)
# =============================================================================

_NEPALI_MONTH_RANGES = (
    ("Baisakh", 4, 14, 5, 14, 0),
    ("Jestha", 5, 15, 6, 14, 0),
    ("Asar", 6, 15, 7, 15, 0),
    ("Shrawan", 7, 16, 8, 16, 0),
    ("Bhadra", 8, 17, 9, 16, 0),
    ("Asoj", 9, 17, 10, 16, 0),
    ("Kartik", 10, 17, 11, 15, 0),
    ("Mangsir", 11, 16, 12, 15, 0),
    ("Poush", 12, 16, 1, 14, 1),
    ("Magh", 1, 15, 2, 12, 0),
    ("Falgun", 2, 13, 3, 14, 0),
    ("Chaitra", 3, 15, 4, 14, 0),
)


def _overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return max((end - start).days + 1, 0)


def _nepali_billing_month(period_start: date, period_end: date) -> str:
    if not period_start or not period_end or period_end < period_start:
        return "-"

    best: tuple[str, int, int] | None = None

    for cycle_year in (period_start.year - 1, period_start.year, period_start.year + 1):
        for name, start_month, start_day, end_month, end_day, end_offset in _NEPALI_MONTH_RANGES:
            range_start = date(cycle_year, start_month, start_day)
            range_end = date(cycle_year + end_offset, end_month, end_day)
            overlap = _overlap_days(period_start, period_end, range_start, range_end)

            if best is None or overlap > best[2]:
                best = (name, cycle_year + 57, overlap)

    if not best or best[2] <= 0:
        return "-"

    return f"{best[0]} {best[1]}"


# =============================================================================
# Shared school header
# =============================================================================


def _draw_school_header(
    c: canvas.Canvas,
    school,
    *,
    page_width: float,
    top_y: float,
    left_margin: float,
    right_margin: float,
    logo_size: float,
    school_name_size: float,
    address_size: float,
    legal_size: float,
) -> float:
    """Draw the reference-style logo-left, centered school identity header."""

    logo_path = _school_logo_source(school)
    logo_x = left_margin
    logo_y = top_y - logo_size
    _draw_image_contain(c, logo_path, logo_x, logo_y, logo_size, logo_size)

    content_left = left_margin + logo_size + 4 * mm
    content_right = page_width - right_margin
    center_x = (content_left + content_right) / 2
    max_width = content_right - content_left

    _draw_centered(
        c,
        _safe_text(getattr(school, "name", None)),
        center_x,
        top_y - 5.2 * mm,
        font_name=FONT_BOLD,
        font_size=school_name_size,
        max_width=max_width,
    )
    _draw_centered(
        c,
        _school_address(school),
        center_x,
        top_y - 12.7 * mm,
        font_size=address_size,
        max_width=max_width,
    )
    _draw_centered(
        c,
        f"PAN: {_school_pan(school)} | Regd. No.: {_school_registration_no(school)}",
        center_x,
        top_y - 19.2 * mm,
        font_size=legal_size,
        max_width=max_width,
    )

    return top_y - max(logo_size, 22 * mm)


# =============================================================================
# Monthly Invoice - exact A5 reference layout
# =============================================================================


def _invoice_particulars(invoice) -> list[tuple[str, str, Decimal]]:
    rows: list[tuple[str, str, Decimal]] = []

    for line in invoice.lines.all():
        particular = (
            getattr(line, "fee_head_name", None)
            or getattr(getattr(line, "fee_head", None), "name", None)
            or getattr(line, "description", None)
            or "-"
        )

        try:
            period = line.get_fee_period_display()
        except (AttributeError, TypeError):
            period = _safe_text(getattr(line, "fee_period", None))

        amount = _as_decimal(getattr(line, "net_amount", getattr(line, "unit_amount", 0)))
        rows.append((_safe_text(particular), _safe_text(period), amount))

    return rows or [("-", "-", Decimal("0"))]


def _draw_invoice_details_table(
    c: canvas.Canvas,
    invoice,
    *,
    x: float,
    top_y: float,
    width: float,
) -> float:
    sn_w = 14 * mm
    particular_w = 53 * mm
    period_w = 32 * mm
    amount_w = width - sn_w - particular_w - period_w

    header_h = 8 * mm
    body_h = 29 * mm
    total_h = 8 * mm
    words_h = 8 * mm

    rows = _invoice_particulars(invoice)
    row_h = max(body_h / max(len(rows), 1), 8 * mm)
    actual_body_h = row_h * len(rows)

    y = top_y
    bottom = y - header_h - actual_body_h - total_h - words_h

    c.setStrokeColor(BLACK)
    c.setLineWidth(0.65)
    c.rect(x, bottom, width, y - bottom, stroke=1, fill=0)

    # Horizontal lines
    header_bottom = y - header_h
    body_bottom = header_bottom - actual_body_h
    total_bottom = body_bottom - total_h
    c.line(x, header_bottom, x + width, header_bottom)
    c.line(x, body_bottom, x + width, body_bottom)
    c.line(x, total_bottom, x + width, total_bottom)

    # Header/body column dividers
    col1 = x + sn_w
    col2 = col1 + particular_w
    col3 = col2 + period_w
    c.line(col1, body_bottom, col1, y)
    c.line(col2, body_bottom, col2, y)
    c.line(col3, total_bottom, col3, y)

    # Header background
    c.setFillColor(LIGHT_GREY)
    c.rect(x, header_bottom, width, header_h, stroke=0, fill=1)
    c.setFillColor(BLACK)

    header_y = header_bottom + 2.4 * mm
    c.setFont(FONT_BOLD, 11)
    c.drawString(x + 2 * mm, header_y, "S.N.")
    c.drawString(col1 + 2 * mm, header_y, "Particular")
    c.drawCentredString((col2 + col3) / 2, header_y, "Period")
    c.drawRightString(x + width - 2 * mm, header_y, "Amount")

    # Body rows
    row_top = header_bottom
    for index, (particular, period, amount) in enumerate(rows, start=1):
        row_bottom = row_top - row_h
        if index < len(rows):
            c.line(x, row_bottom, x + width, row_bottom)

        text_y = row_top - 5.2 * mm
        c.setFont(FONT_REGULAR, 11)
        c.drawString(x + 2 * mm, text_y, f"{index}.")

        particular_size = _fit_font_size(particular, particular_w - 4 * mm, 11, minimum_size=8)
        c.setFont(FONT_REGULAR, particular_size)
        c.drawString(col1 + 2 * mm, text_y, particular)

        period_size = _fit_font_size(period, period_w - 4 * mm, 11, minimum_size=8)
        c.setFont(FONT_REGULAR, period_size)
        c.drawString(col2 + 2 * mm, text_y, period)

        c.setFont(FONT_REGULAR, 11)
        c.drawRightString(x + width - 2 * mm, text_y, _money(amount))
        row_top = row_bottom

    # Total row
    total_y = total_bottom + 2.4 * mm
    c.setFont(FONT_REGULAR, 11)
    c.drawRightString(col3 - 2 * mm, total_y, "Total")
    c.setFont(FONT_BOLD, 11)
    c.drawRightString(x + width - 2 * mm, total_y, _money(invoice.total_amount))

    # In words row
    words_y = bottom + 2.4 * mm
    c.setFont(FONT_BOLD, 11)
    c.drawString(x + 2 * mm, words_y, "In Words:")
    label_width = stringWidth("In Words:", FONT_BOLD, 11) + 2
    in_words = _amount_in_words(invoice.total_amount)
    in_words_size = _fit_font_size(in_words, width - label_width - 5 * mm, 11, minimum_size=8)
    c.setFont(FONT_REGULAR, in_words_size)
    c.drawString(x + 2 * mm + label_width, words_y, in_words)

    return bottom


def _draw_monthly_invoice_page(c: canvas.Canvas, invoice) -> None:
    page_width, page_height = A5
    left = 6 * mm
    right = 6 * mm
    content_width = page_width - left - right
    logo_path = _school_logo_source(invoice.school)

    # Header
    top = page_height - 7 * mm
    header_bottom = _draw_school_header(
        c,
        invoice.school,
        page_width=page_width,
        top_y=top,
        left_margin=left,
        right_margin=right,
        logo_size=24 * mm,
        school_name_size=14,
        address_size=10,
        legal_size=10,
    )

    # Full-width title bar
    title_top = header_bottom - 6 * mm
    title_h = 10 * mm
    c.setFillColor(LIGHT_GREY)
    c.rect(left, title_top - title_h, content_width, title_h, stroke=0, fill=1)
    c.setFillColor(BLACK)
    _draw_centered(
        c,
        "MONTHLY INVOICE",
        page_width / 2,
        title_top - 7.2 * mm,
        font_name=FONT_BOLD,
        font_size=14,
        max_width=content_width - 8 * mm,
    )

    # Information block
    info_top = title_top - title_h - 11 * mm
    left_x = left
    middle_x = left + 56 * mm
    right_x = left + 89 * mm
    line_gap = 8 * mm

    _draw_label_value(c, left_x, info_top, "Student Name", _student_name(invoice.student), max_width=73 * mm)
    _draw_label_value(c, right_x, info_top, "Regd No.", _student_registration_no(invoice.student), max_width=content_width - (right_x - left))

    _draw_label_value(c, left_x, info_top - line_gap, "Class", _safe_text(getattr(invoice.academic_class, "name", invoice.academic_class)), max_width=47 * mm)
    _draw_label_value(c, middle_x, info_top - line_gap, "Section", _section_name(invoice.enrollment), max_width=34 * mm)
    _draw_label_value(c, right_x, info_top - line_gap, "Phone", _display_phone(getattr(invoice.student, "phone", None)), max_width=content_width - (right_x - left))

    _draw_label_value(c, left_x, info_top - 2 * line_gap, "Month", _nepali_billing_month(invoice.period_start, invoice.period_end), max_width=76 * mm)
    _draw_label_value(c, right_x, info_top - 2 * line_gap, "Currency", invoice.currency, max_width=content_width - (right_x - left))

    _draw_label_value(c, left_x, info_top - 3 * line_gap, "Invoice Date", invoice.invoice_date.strftime("%Y-%m-%d"), max_width=75 * mm)
    _draw_label_value(c, left_x, info_top - 4 * line_gap, "Invoice No.", invoice.invoice_number, max_width=content_width)

    # Watermark behind table/details
    _draw_logo_watermark(
        c,
        logo_path,
        page_width / 2,
        page_height * 0.47,
        66 * mm,
        alpha=0.065,
    )

    table_top = info_top - 5 * line_gap - 3 * mm
    table_bottom = _draw_invoice_details_table(
        c,
        invoice,
        x=left,
        top_y=table_top,
        width=content_width,
    )

    # Authorized signature
    signature_right = page_width - right
    signature_y = table_bottom - 18 * mm

    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.line(
        signature_right - 40 * mm,
        signature_y + 7 * mm,
        signature_right,
        signature_y + 7 * mm,
    )

    _draw_centered(
        c,
        "Authorized Signature",
        signature_right - 20 * mm,
        signature_y,
        font_size=11,
        max_width=42 * mm,
    )

    # Note — positioned relative to the invoice table/signature
    note_y = signature_y - 12 * mm
    note = _safe_text(
        getattr(invoice, "notes", None)
    )

    c.setFont(FONT_BOLD_OBLIQUE, 11)
    c.drawString(
        left + 31 * mm,
        note_y,
        "Note:",
    )

    note_x = left + 44 * mm
    note_width = page_width - right - note_x

    note_size = _fit_font_size(
        note,
        note_width,
        11,
        font_name=FONT_OBLIQUE,
        minimum_size=8,
    )

    c.setFont(FONT_OBLIQUE, note_size)
    c.drawString(
        note_x,
        note_y,
        note,
    )

    # Footer
    footer_line_y = 12 * mm
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.6)
    c.line(left, footer_line_y, page_width - right, footer_line_y)

    footer_contact = f"Phone: {_school_phone(invoice.school)} | Email: {_school_email(invoice.school)}"
    _draw_centered(
        c,
        footer_contact,
        page_width / 2,
        13.8 * mm,
        font_size=11,
        max_width=content_width,
    )
    _draw_centered(
        c,
        "This is computer generated invoice.",
        page_width / 2,
        7.2 * mm,
        font_name=FONT_OBLIQUE,
        font_size=11,
        max_width=content_width,
    )


# =============================================================================
# Receipt - exact A4, first and second copy layout
# =============================================================================


def _receipt_particulars(payment, allocations: Iterable[FeePaymentAllocation]) -> list[tuple[str, Decimal]]:
    rows: list[tuple[str, Decimal]] = []

    for allocation in allocations:
        invoice = allocation.invoice
        particular = _safe_text(getattr(invoice, "notes", None), fallback="")
        if not particular:
            month = _nepali_billing_month(invoice.period_start, invoice.period_end)
            particular = f"{month} fee"
        rows.append((particular, _as_decimal(allocation.amount)))

    if not rows:
        rows.append(("Advance fee payment", _as_decimal(payment.amount)))

    return rows


def _draw_receipt_table(
    c: canvas.Canvas,
    rows: list[tuple[str, Decimal]],
    *,
    x: float,
    top_y: float,
    width: float,
    total_amount: Any,
) -> float:
    sn_w = 20 * mm
    amount_w = 48 * mm
    particular_w = width - sn_w - amount_w

    header_h = 7.5 * mm
    body_h = 15 * mm
    total_h = 6.5 * mm
    words_h = 6.5 * mm
    row_h = max(body_h / max(len(rows), 1), 6.5 * mm)
    actual_body_h = row_h * len(rows)

    y = top_y
    bottom = y - header_h - actual_body_h - total_h - words_h
    header_bottom = y - header_h
    body_bottom = header_bottom - actual_body_h
    total_bottom = body_bottom - total_h

    c.setStrokeColor(BLACK)
    c.setLineWidth(0.55)
    c.rect(x, bottom, width, y - bottom, stroke=1, fill=0)
    c.line(x, header_bottom, x + width, header_bottom)
    c.line(x, body_bottom, x + width, body_bottom)
    c.line(x, total_bottom, x + width, total_bottom)

    col1 = x + sn_w
    col2 = col1 + particular_w
    c.line(col1, body_bottom, col1, y)
    c.line(col2, total_bottom, col2, y)

    c.setFillColor(LIGHT_GREY)
    c.rect(x, header_bottom, width, header_h, stroke=0, fill=1)
    c.setFillColor(BLACK)

    header_text_y = header_bottom + 2.2 * mm
    c.setFont(FONT_BOLD, 12)
    c.drawString(x + 2 * mm, header_text_y, "S.N.")
    c.drawString(col1 + 2 * mm, header_text_y, "Particular")
    c.drawRightString(x + width - 2 * mm, header_text_y, "Amount")

    row_top = header_bottom
    for index, (particular, amount) in enumerate(rows, start=1):
        row_bottom = row_top - row_h
        if index < len(rows):
            c.line(x, row_bottom, x + width, row_bottom)
        text_y = row_top - 4.8 * mm
        c.setFont(FONT_REGULAR, 12)
        c.drawString(x + 2 * mm, text_y, f"{index}.")
        part_size = _fit_font_size(particular, particular_w - 4 * mm, 12, minimum_size=8)
        c.setFont(FONT_REGULAR, part_size)
        c.drawString(col1 + 2 * mm, text_y, particular)
        c.setFont(FONT_REGULAR, 12)
        c.drawRightString(x + width - 2 * mm, text_y, _money(amount))
        row_top = row_bottom

    total_y = total_bottom + 1.9 * mm
    c.setFont(FONT_REGULAR, 12)
    c.drawRightString(col2 - 2 * mm, total_y, "Total")
    c.setFont(FONT_BOLD, 12)
    c.drawRightString(x + width - 2 * mm, total_y, _money(total_amount))

    words_y = bottom + 1.9 * mm
    c.setFont(FONT_BOLD, 12)
    c.drawString(x + 2 * mm, words_y, "In Words:")
    label_width = stringWidth("In Words:", FONT_BOLD, 12) + 2
    words = _amount_in_words(total_amount)
    size = _fit_font_size(words, width - label_width - 5 * mm, 12, minimum_size=8)
    c.setFont(FONT_REGULAR, size)
    c.drawString(x + 2 * mm + label_width, words_y, words)

    return bottom


def _draw_receipt_copy(
    c: canvas.Canvas,
    payment,
    allocations: list[FeePaymentAllocation],
    *,
    copy_label: str,
    top_y: float,
    block_height: float,
) -> None:
    page_width, _ = A4
    left = 4 * mm
    right = 4 * mm
    content_width = page_width - left - right
    logo_path = _school_logo_source(payment.school)

    header_top = top_y - 1 * mm
    header_bottom = _draw_school_header(
        c,
        payment.school,
        page_width=page_width,
        top_y=header_top,
        left_margin=left,
        right_margin=right,
        logo_size=23 * mm,
        school_name_size=18,
        address_size=12,
        legal_size=12,
    )

    # Copy label + receipt title strip
    strip_top = header_bottom - 2.5 * mm
    strip_h = 7.5 * mm
    c.setFillColor(LIGHT_GREY)
    c.rect(left, strip_top - strip_h, content_width, strip_h, stroke=0, fill=1)
    c.setFillColor(BLACK)
    c.setFont(FONT_BOLD, 12)
    c.drawString(left + 3 * mm, strip_top - 5.3 * mm, copy_label)
    c.drawCentredString(page_width / 2, strip_top - 5.3 * mm, "RECEIPT")

    # Student/payment details
    details_top = strip_top - strip_h - 5 * mm
    left_col_x = left
    right_col_x = page_width / 2 + 2 * mm
    line_gap = 6.2 * mm
    left_width = page_width / 2 - left - 5 * mm
    right_width = page_width - right - right_col_x

    paid_at = timezone.localtime(payment.paid_at).strftime("%Y-%m-%d %I:%M %p")
    first_allocation = allocations[0] if allocations else None
    reference = payment.external_reference or payment.receipt_number

    _draw_label_value(c, left_col_x, details_top, "Student Name", _student_name(payment.student), max_width=left_width)
    _draw_label_value(c, right_col_x, details_top, "Receipt No.", _student_registration_no(payment.student), max_width=right_width)

    _draw_label_value(c, left_col_x, details_top - line_gap, "Class", _safe_text(getattr(payment.academic_class, "name", payment.academic_class)), max_width=left_width)
    _draw_label_value(c, right_col_x, details_top - line_gap, "Phone", _display_phone(getattr(payment.student, "phone", None)), max_width=right_width)

    _draw_label_value(c, left_col_x, details_top - 2 * line_gap, "Paid At", paid_at, max_width=left_width)
    _draw_label_value(c, right_col_x, details_top - 2 * line_gap, "Address", _safe_text(getattr(payment.student, "address", None), fallback=_school_address(payment.school)), max_width=right_width)

    _draw_label_value(c, left_col_x, details_top - 3 * line_gap, "Currency", payment.currency, max_width=left_width)
    _draw_label_value(c, right_col_x, details_top - 3 * line_gap, "Method", payment.get_payment_method_display(), max_width=right_width)

    _draw_label_value(c, left_col_x, details_top - 4 * line_gap, "Reference", reference, max_width=left_width)
    _draw_label_value(c, right_col_x, details_top - 4 * line_gap, "Received By", _display_user_name(payment.received_by), max_width=right_width)

    # Watermark behind table
    table_top = details_top - 5 * line_gap - 1.5 * mm
    _draw_logo_watermark(
        c,
        logo_path,
        page_width / 2,
        table_top - 16 * mm,
        49 * mm,
        alpha=0.055,
    )

    rows = _receipt_particulars(payment, allocations)
    table_bottom = _draw_receipt_table(
        c,
        rows,
        x=left,
        top_y=table_top,
        width=content_width,
        total_amount=payment.amount,
    )

    # Signature/stamp areas
    signature_y = table_bottom - 24 * mm
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.7)
    c.setDash(1.1, 1.1)
    c.line(left, signature_y + 7 * mm, left + 45 * mm, signature_y + 7 * mm)
    c.line(page_width - right - 59 * mm, signature_y + 7 * mm, page_width - right - 14 * mm, signature_y + 7 * mm)
    c.setDash()

    c.setFont(FONT_REGULAR, 12)
    c.drawString(left, signature_y, "Received By")
    c.drawString(page_width - right - 59 * mm, signature_y, "School Stamp")

    _draw_centered(
        c,
        "This is computer generated receipt.",
        page_width / 2,
        top_y - block_height + 7 * mm,
        font_size=12,
        max_width=content_width,
    )


def _draw_receipt_page(c: canvas.Canvas, payment) -> None:
    allocations = list(
        FeePaymentAllocation.objects.select_related("invoice")
        .filter(payment=payment)
        .order_by("created_at")
    )

    page_width, page_height = A4
    top_margin = 4 * mm
    separator_y = page_height / 2
    block_height = page_height / 2 - top_margin

    _draw_receipt_copy(
        c,
        payment,
        allocations,
        copy_label="First Copy",
        top_y=page_height - top_margin,
        block_height=block_height,
    )

    # Dotted divider
    c.saveState()
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.7)
    c.setDash(1.1, 1.1)
    c.line(4 * mm, separator_y, page_width - 4 * mm, separator_y)
    c.restoreState()

    _draw_receipt_copy(
        c,
        payment,
        allocations,
        copy_label="Second Copy",
        top_y=separator_y - 1 * mm,
        block_height=block_height,
    )


# =============================================================================
# Database reload helpers
# =============================================================================


def _reload_invoice(invoice):
    select_related = [
        "school",
        "student",
        "batch",
        "academic_class",
        "enrollment",
        "generated_by",
    ]

    # section is nullable and may not exist in some projects.
    try:
        return (
            invoice.__class__.objects
            .select_related(*select_related, "enrollment__section")
            .prefetch_related("lines")
            .get(pk=invoice.pk)
        )
    except Exception:
        return (
            invoice.__class__.objects
            .select_related(*select_related)
            .prefetch_related("lines")
            .get(pk=invoice.pk)
        )


def _reload_payment(payment):
    return (
        payment.__class__.objects
        .select_related(
            "school",
            "student",
            "batch",
            "academic_class",
            "enrollment",
            "received_by",
        )
        .get(pk=payment.pk)
    )


# =============================================================================
# Public builders used by API views
# =============================================================================


def build_invoice_pdf(invoice) -> bytes:
    """Generate one A5 monthly invoice matching the approved reference."""
    invoice = _reload_invoice(invoice)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A5, pageCompression=1)
    c.setTitle(invoice.invoice_number)
    c.setAuthor("School Fee Management System")
    _draw_monthly_invoice_page(c, invoice)
    c.showPage()
    c.save()
    return buffer.getvalue()


def build_bulk_invoice_pdf(invoices) -> bytes:
    """Generate one A5 page per monthly invoice in a combined PDF."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A5, pageCompression=1)
    c.setTitle("Bulk Monthly Invoices")
    c.setAuthor("School Fee Management System")

    for invoice in invoices:
        loaded = _reload_invoice(invoice)
        _draw_monthly_invoice_page(c, loaded)
        c.showPage()

    c.save()
    return buffer.getvalue()


def build_payment_receipt_pdf(payment) -> bytes:
    """Generate one A4 receipt containing First Copy and Second Copy."""
    payment = _reload_payment(payment)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    c.setTitle(payment.receipt_number)
    c.setAuthor("School Fee Management System")
    _draw_receipt_page(c, payment)
    c.showPage()
    c.save()
    return buffer.getvalue()
