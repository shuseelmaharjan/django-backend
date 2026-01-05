from rest_framework import generics, permissions
from filehandler.models import UploadedFile
from filehandler.serializers import UploadedFileSerializer
from drf_spectacular.utils import extend_schema
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

class BaseUploadView(generics.CreateAPIView):
    serializer_class = UploadedFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    is_temporary_value: bool = True

    def perform_create(self, serializer):
        try:
            serializer.save(is_temporary=self.is_temporary_value)
        except DjangoValidationError as e:
            # convert model validation errors -> DRF 400
            if hasattr(e, "message_dict"):
                raise DRFValidationError(e.message_dict)
            raise DRFValidationError({"detail": e.messages})

@extend_schema(
    tags=["File Handler"],
    summary="Upload temporary file",
    description="Uploads a file marked as temporary (auto-cleanup later).",
)
class TemporaryUploadView(BaseUploadView):
    """
    POST: creates a file with is_temporary=True
    """
    is_temporary_value = True

@extend_schema(
    tags=["File Handler"],
    summary="Upload permanent file",
    description="Uploads a file marked as permanent.",
)
class PermanentUploadView(BaseUploadView):
    """
    POST: creates a file with is_temporary=False
    """
    is_temporary_value = False

@extend_schema(
    tags=["File Handler"],
    summary="Delete file",
    description="Deletes a file and removes it from storage.",
)
class FileDeleteView(generics.DestroyAPIView):
    """
    DELETE: removes DB row and deletes the actual file via model.delete()
    """
    permission_classes = [permissions.IsAuthenticated]
    queryset = UploadedFile.objects.all()
    lookup_field = "id"

    # Optional: only allow owners (or staff) to delete
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return qs
        return qs.filter(uploaded_by=user)
