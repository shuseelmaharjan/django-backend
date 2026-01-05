from django.urls import path
from filehandler.views import TemporaryUploadView, PermanentUploadView, FileDeleteView

app_name = "file-handler"

urlpatterns = [
    path("v1/files/temp-upload/", TemporaryUploadView.as_view(), name="file-upload-temp"),
    path("v1/files/upload/", PermanentUploadView.as_view(), name="file-upload-permanent"),
    path("v1/remove-file/<uuid:id>/", FileDeleteView.as_view(), name="file-delete"),
]
