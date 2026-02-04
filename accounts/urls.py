# accounts/urls.py
from django.urls import path

from .views import (
    ForgotPasswordSendOTPView,
    ForgotPasswordVerifyOTPView,
    ForgotPasswordResetView, ChangePasswordView,
)

urlpatterns = [
    path("auth/password/forgot/", ForgotPasswordSendOTPView.as_view(), name="forgot-password-send-otp"),
    path("auth/password/verify-otp/", ForgotPasswordVerifyOTPView.as_view(), name="forgot-password-verify-otp"),
    path("auth/password/reset/", ForgotPasswordResetView.as_view(), name="forgot-password-reset"),
    path("auth/password/change/", ChangePasswordView.as_view(), name="change-password"),

]
