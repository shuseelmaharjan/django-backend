# filehandler/validators.py
import os
from django.core.exceptions import ValidationError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
PDF_EXTS = {".pdf"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
DOC_EXTS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"}

DEFAULT_MAX_MB = {
    "image": 10,
    "pdf": 25,
    "audio": 50,
    "video": 250,
    "document": 25,
    "other": 25,
}

def _ext(name: str) -> str:
    return os.path.splitext(name.lower())[1]

def detect_file_type(filename: str) -> str:
    e = _ext(filename)
    if e in IMAGE_EXTS:
        return "image"
    if e in PDF_EXTS:
        return "pdf"
    if e in AUDIO_EXTS:
        return "audio"
    if e in VIDEO_EXTS:
        return "video"
    if e in DOC_EXTS:
        return "document"
    return "other"

def validate_upload(file_obj, *, file_type: str, max_mb: int | None = None):
    max_mb = max_mb or DEFAULT_MAX_MB.get(file_type, 25)
    max_bytes = max_mb * 1024 * 1024

    if file_obj.size > max_bytes:
        raise ValidationError(f"File too large. Max allowed for {file_type} is {max_mb} MB.")

    filename = getattr(file_obj, "name", "")
    e = _ext(filename)

    if file_type == "image" and e not in IMAGE_EXTS:
        raise ValidationError("Invalid image file extension.")
    if file_type == "pdf" and e not in PDF_EXTS:
        raise ValidationError("Invalid PDF file extension.")
    if file_type == "audio" and e not in AUDIO_EXTS:
        raise ValidationError("Invalid audio file extension.")
    if file_type == "video" and e not in VIDEO_EXTS:
        raise ValidationError("Invalid video file extension.")
    if file_type == "document" and e not in DOC_EXTS:
        raise ValidationError("Invalid document file extension.")
