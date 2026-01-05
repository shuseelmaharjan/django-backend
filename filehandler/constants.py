# filehandler/constants.py
from django.db import models

class FileType(models.TextChoices):
    IMAGE = "image", "Image"
    PDF = "pdf", "PDF"
    AUDIO = "audio", "Audio"
    VIDEO = "video", "Video"
    DOCUMENT = "document", "Document"   # doc/docx/xls/xlsx/ppt/pptx
    OTHER = "other", "Other"
