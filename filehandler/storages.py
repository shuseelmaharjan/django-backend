# filehandler/storages.py
from django.conf import settings
from django.core.files.storage import FileSystemStorage

try:
    # Optional S3 support
    from storages.backends.s3boto3 import S3Boto3Storage
    HAS_S3 = True
except ImportError:
    HAS_S3 = False


# -----------------------------
# Local filesystem storages
# -----------------------------

class LocalPublicMediaStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(
            location=settings.MEDIA_ROOT,
            base_url=settings.MEDIA_URL,
        )


class LocalPrivateMediaStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(
            location=getattr(settings, "PRIVATE_MEDIA_ROOT", settings.MEDIA_ROOT),
            base_url=None,  # no public URL
        )


# -----------------------------
# S3 / Cloud storages
# -----------------------------

if HAS_S3:
    class S3PublicMediaStorage(S3Boto3Storage):
        location = "media/public"
        default_acl = "public-read"
        file_overwrite = False
        custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)

    class S3PrivateMediaStorage(S3Boto3Storage):
        location = "media/private"
        default_acl = "private"
        file_overwrite = False
        custom_domain = None
        querystring_auth = True  # signed URLs
else:
    S3PublicMediaStorage = None
    S3PrivateMediaStorage = None


# -----------------------------
# Public API used by models
# -----------------------------

def PublicMediaStorage():
    """
    Returns correct public storage backend based on settings.
    """
    if HAS_S3 and getattr(settings, "USE_S3", False):
        return S3PublicMediaStorage()
    return LocalPublicMediaStorage()


def PrivateMediaStorage():
    """
    Returns correct private storage backend based on settings.
    """
    if HAS_S3 and getattr(settings, "USE_S3", False):
        return S3PrivateMediaStorage()
    return LocalPrivateMediaStorage()
