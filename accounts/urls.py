# accounts/urls.py
from django.urls import path

from .views import (
    ForgotPasswordSendOTPView,
    ForgotPasswordVerifyOTPView,
    ForgotPasswordResetView, ChangePasswordView, MyProfileView,
    MyProfileBasicInfoUpdateView,
    MyProfilePictureUpdateView,
    EmailChangeSendOTPView,
    EmailChangeVerifyOTPView,
)

urlpatterns = [
    path("auth/password/forgot/", ForgotPasswordSendOTPView.as_view(), name="forgot-password-send-otp"),
    path("auth/password/verify-otp/", ForgotPasswordVerifyOTPView.as_view(), name="forgot-password-verify-otp"),
    path("auth/password/reset/", ForgotPasswordResetView.as_view(), name="forgot-password-reset"),
    path("auth/password/change/", ChangePasswordView.as_view(), name="change-password"),
    # Profile
    path(
        "account/me/",
        MyProfileView.as_view(),
        name="my-profile",
    ),
    path(
        "account/me/basic-info/",
        MyProfileBasicInfoUpdateView.as_view(),
        name="my-profile-basic-info-update",
    ),
    path(
        "account/me/profile-picture/",
        MyProfilePictureUpdateView.as_view(),
        name="my-profile-picture-update",
    ),

    # Email change
    path(
        "account/me/email/change/request/",
        EmailChangeSendOTPView.as_view(),
        name="email-change-send-otp",
    ),
    path(
        "account/me/email/change/verify/",
        EmailChangeVerifyOTPView.as_view(),
        name="email-change-verify-otp",
    ),

]
