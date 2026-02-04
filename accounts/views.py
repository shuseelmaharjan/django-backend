# accounts/views.py
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated

from drf_spectacular.utils import OpenApiResponse, OpenApiExample

from common.schema import schema
from accounts.serializers.password_reset import (
    ForgotPasswordSendOTPSerializer,
    ForgotPasswordVerifyOTPSerializer,
    ForgotPasswordResetSerializer, ChangePasswordSerializer,
)


class ForgotPasswordSendOTPView(APIView):
    permission_classes = [AllowAny]

    @schema(
        tag="01. Auth",
        summary="Forgot password: send OTP to email",
        request=ForgotPasswordSendOTPSerializer,
        responses={
            200: OpenApiResponse(
                description="Always returns success to avoid user enumeration.",
                examples=[OpenApiExample("Sent", value={"sent": True})],
            )
        },
    )
    def post(self, request):
        ser = ForgotPasswordSendOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        out = ser.save()
        return Response({
            "sent": out["sent"],
            "message": "If the email exists, an OTP has been sent."
        }, status=status.HTTP_200_OK)


class ForgotPasswordVerifyOTPView(APIView):
    permission_classes = [AllowAny]

    @schema(
        tag="01. Auth",
        summary="Forgot password: verify OTP",
        request=ForgotPasswordVerifyOTPSerializer,
        responses={
            200: OpenApiResponse(
                description="OTP verified, reset token issued.",
                examples=[
                    OpenApiExample(
                        "Verified",
                        value={
                            "reset_token": "b3d7a9e9-60ad-4c5a-9b10-2af3f0e81f8d",
                            "reset_token_expires_at": "2026-02-02T12:45:00Z",
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Invalid / expired OTP"),
        },
    )
    def post(self, request):
        ser = ForgotPasswordVerifyOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(
            {
                "reset_token": ser.validated_data["reset_token"],
                "reset_token_expires_at": ser.validated_data["reset_token_expires_at"],
            },
            status=status.HTTP_200_OK,
        )


class ForgotPasswordResetView(APIView):
    permission_classes = [AllowAny]

    @schema(
        tag="01. Auth",
        summary="Forgot password: set new password (requires reset_token)",
        request=ForgotPasswordResetSerializer,
        responses={
            200: OpenApiResponse(
                description="Password reset success",
                examples=[OpenApiExample("Reset", value={"reset": True})],
            ),
            400: OpenApiResponse(description="Invalid token or weak password"),
        },
    )
    def post(self, request):
        ser = ForgotPasswordResetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        out = ser.save()
        return Response(
            {
                "reset": out["reset"],
                "message": "Password has been reset successfully.",
            },
            status=status.HTTP_200_OK,
        )

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @schema(
        tag="01. Auth",
        summary="Change password (requires login)",
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(
                description="Password changed successfully.",
                examples=[OpenApiExample("Changed", value={"changed": True, "message": "Password changed successfully."})],
            ),
            400: OpenApiResponse(description="Validation error (wrong old password / weak password / mismatch)."),
            401: OpenApiResponse(description="Unauthorized."),
        },
    )
    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        out = ser.save()
        return Response(
            {"changed": out["changed"], "message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )