# filehandler/utils.py
import uuid
import datetime
import os

def upload_to(instance, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    today = datetime.date.today()

    # Put files under: media/uploads/<type>/<year>/<month>/<uuid>.<ext>
    ftype = instance.file_type or "other"
    new_filename = f"{uuid.uuid4()}{ext}"
    return f"uploads/{ftype}/{today.year}/{today.month:02d}/{new_filename}"
