from rest_framework import generics, permissions
from filehandler.models import UploadedFile
from filehandler.serializers import UploadedFileSerializer
from drf_spectacular.utils import extend_schema
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.http import FileResponse, Http404
from common.permissions import IsAuthenticatedAndActive
from django.db.models import Q
from django.shortcuts import get_object_or_404

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
    tags=["META File Handler"],
    summary="Upload temporary file",
    description="Uploads a file marked as temporary (auto-cleanup later).",
)
class TemporaryUploadView(BaseUploadView):
    """
    POST: creates a file with is_temporary=True
    """
    is_temporary_value = True

@extend_schema(
    tags=["META File Handler"],
    summary="Upload permanent file",
    description="Uploads a file marked as permanent.",
)
class PermanentUploadView(BaseUploadView):
    """
    POST: creates a file with is_temporary=False
    """
    is_temporary_value = False

@extend_schema(
    tags=["META File Handler"],
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

class FileDownloadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndActive]
    queryset = UploadedFile.objects.all()
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # allow staff/superuser full access
        if user.is_staff or user.is_superuser:
            return qs
        # allow the owner or files that are not associated with any user (public files)
        return qs.filter(Q(uploaded_by=user) | Q(uploaded_by__isnull=True))

    def get_object(self):
        # Resolve the lookup value from URL and search within the filtered queryset
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        if lookup_value is None:
            raise Http404("Missing lookup parameter")
        # Use get_object_or_404 so we return a 404 with the standard message when not found
        obj = get_object_or_404(queryset, **{self.lookup_field: lookup_value})
        self.check_object_permissions(self.request, obj)
        return obj

    def get(self, request, *args, **kwargs):
        obj: UploadedFile = self.get_object()

        if not obj.file:
            raise Http404("File not found")

        filename = obj.original_name or obj.file.name.split("/")[-1]
        return FileResponse(obj.file.open("rb"), as_attachment=True, filename=filename)