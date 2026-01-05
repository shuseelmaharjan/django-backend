# filehandler/fields.py
from django.db.models import FileField
from filehandler.storages import PublicMediaStorage, PrivateMediaStorage

class DynamicStorageFileField(FileField):
    """
    Uses public or private storage based on instance.is_public.
    Works with S3 or local storages.
    """
    def _select_storage(self, instance):
        return PublicMediaStorage() if getattr(instance, "is_public", False) else PrivateMediaStorage()

    def pre_save(self, model_instance, add):
        file = super().pre_save(model_instance, add)
        # ensure storage set correctly before saving
        if file and model_instance:
            file.storage = self._select_storage(model_instance)
        return file
