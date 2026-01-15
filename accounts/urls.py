# accounts/urls.py
from django.urls import path
from .views import (
    ChangePasswordView,
    ProfileGetView,
)

urlpatterns = [
    path("change-password/", ChangePasswordView.as_view(), name="authx-change-password"),
    # 1 GET
    path("my-profile/", ProfileGetView.as_view(), name="authx-profile-get"),

    # 3 POST (separate)
    # path("change-email/", UpdateEmailView.as_view(), name="authx-profile-update-email"),
    # path("change-username/", UpdateUsernameView.as_view(), name="authx-profile-update-username"),
    # path("change-phone/", UpdatePhoneView.as_view(), name="authx-profile-update-phone"),
]
