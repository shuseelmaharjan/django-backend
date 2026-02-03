# accounts/serializers/password_reset.py
import uuid

from django.utils import timezone
from django.db import transaction
from django.conf import settings
from rest_framework import serializers

from accounts.models import User, PasswordResetOTP
from accounts.utils import (
    generate_numeric_otp,
    hash_otp,
    verify_otp,
    validate_strong_password,
)
from smtp.services import send_html_template_email


# ---------------------------
# 1) SEND OTP
# ---------------------------
class ForgotPasswordSendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()

    def create(self, validated_data):
        email = validated_data["email"]

        # Avoid user enumeration: always return sent=True.
        user = (
            User.objects.filter(email=email, is_deleted=False)
            .only("id", "email", "first_name")
            .first()
        )

        if not user or not user.email:
            return {"sent": True}

        # Generate OTP and create OTP record
        otp = generate_numeric_otp()

        otp_obj = PasswordResetOTP.objects.create(
            user=user,
            email=email,
            otp_hash="",  # set after we get id for salt
            expires_at=PasswordResetOTP.default_expiry(),
        )

        otp_obj.otp_hash = hash_otp(otp, salt=str(otp_obj.id))
        otp_obj.save(update_fields=["otp_hash"])

        # Send OTP email after commit
        subject = f"{settings.APP_NAME} password reset OTP"
        context = {
            "app_name": settings.APP_NAME,
            "first_name": user.first_name or "there",
            "otp": otp,
            "expires_minutes": 10,
        }
        text_fallback = (
            f"Hi {context['first_name']},\n\n"
            f"Your OTP for password reset is: {otp}\n"
            f"It expires in {context['expires_minutes']} minutes.\n\n"
            f"If you didn't request this, you can ignore this email."
        )

        def _safe_send():
            try:
                send_html_template_email(
                    subject=subject,
                    template_name="smtp/password_reset_otp.html",
                    context=context,
                    recipients=[email],
                    text_fallback=text_fallback,
                )
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Failed to send password reset OTP email",
                    extra={"user_id": str(user.id), "email": email},
                )

        transaction.on_commit(_safe_send)

        return {"sent": True}


# ---------------------------
# 2) VERIFY OTP -> ISSUE RESET TOKEN
# ---------------------------
class ForgotPasswordVerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=4, max_length=10)

    reset_token = serializers.UUIDField(read_only=True)
    reset_token_expires_at = serializers.DateTimeField(read_only=True)

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        email = attrs["email"]
        otp = attrs["otp"].strip()

        otp_obj = (
            PasswordResetOTP.objects.filter(
                email=email,
                is_used=False,
                expires_at__gt=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )

        if not otp_obj:
            raise serializers.ValidationError({"otp": "Invalid or expired OTP."})

        if otp_obj.attempts >= otp_obj.max_attempts:
            raise serializers.ValidationError({"otp": "Too many attempts. Please request a new OTP."})

        ok = verify_otp(otp, otp_obj.otp_hash, salt=str(otp_obj.id))

        otp_obj.attempts += 1
        otp_obj.save(update_fields=["attempts"])

        if not ok:
            raise serializers.ValidationError({"otp": "Invalid or expired OTP."})

        otp_obj.verified_at = timezone.now()
        otp_obj.reset_token = uuid.uuid4()
        otp_obj.reset_token_expires_at = PasswordResetOTP.default_reset_token_expiry()
        otp_obj.save(update_fields=["verified_at", "reset_token", "reset_token_expires_at"])

        attrs["reset_token"] = otp_obj.reset_token
        attrs["reset_token_expires_at"] = otp_obj.reset_token_expires_at
        return attrs


# ---------------------------
# 3) RESET PASSWORD (via reset_token) + SEND SUCCESS EMAIL
# ---------------------------
class ForgotPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reset_token = serializers.UUIDField()
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        email = attrs["email"]
        reset_token = attrs["reset_token"]
        new_password = attrs["new_password"]

        otp_obj = (
            PasswordResetOTP.objects.select_related("user")
            .filter(
                email=email,
                reset_token=reset_token,
                is_used=False,
                reset_token_expires_at__gt=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )

        if not otp_obj:
            raise serializers.ValidationError({"reset_token": "Invalid or expired reset token."})

        validate_strong_password(new_password, user=otp_obj.user)

        attrs["_otp_obj"] = otp_obj
        return attrs

    def create(self, validated_data):
        otp_obj = validated_data["_otp_obj"]
        user = otp_obj.user
        new_password = validated_data["new_password"]

        user.set_password(new_password)
        user.save(update_fields=["password"])

        otp_obj.is_used = True
        otp_obj.mark_used()

        PasswordResetOTP.objects.filter(
            user=user,
            email=validated_data["email"],
            is_used=False,
        ).exclude(id=otp_obj.id).update(is_used=True)

        # Send success email after commit
        if user.email:
            def _send_confirmation():
                try:
                    send_html_template_email(
                        subject=f"{settings.APP_NAME} password changed successfully",
                        template_name="smtp/password_reset_success.html",
                        context={
                            "app_name": settings.APP_NAME,
                            "first_name": user.first_name or "there",
                        },
                        recipients=[user.email],
                        text_fallback=(
                            f"Hi {user.first_name or 'there'},\n\n"
                            "Your password has been changed successfully.\n\n"
                            "If you did not perform this action, please contact support immediately."
                        ),
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Failed to send password reset success email",
                        extra={"user_id": str(user.id), "email": user.email},
                    )

            transaction.on_commit(_send_confirmation)

        return {"reset": True}


# ---------------------------
# 4) CHANGE PASSWORD (logged-in user) + SEND SUCCESS EMAIL
# ---------------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, min_length=1, max_length=128)
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    confirm_password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        old_password = attrs["old_password"]
        new_password = attrs["new_password"]
        confirm_password = attrs["confirm_password"]

        if not user.check_password(old_password):
            raise serializers.ValidationError({"old_password": "Old password is incorrect."})

        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        if old_password == new_password:
            raise serializers.ValidationError({"new_password": "New password must be different from old password."})

        validate_strong_password(new_password, user=user)

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        new_password = validated_data["new_password"]
        user.set_password(new_password)
        user.save(update_fields=["password"])

        if user.email:
            def _send_confirmation():
                try:
                    send_html_template_email(
                        subject=f"{settings.APP_NAME} password changed successfully",
                        template_name="smtp/password_change_success.html",
                        context={
                            "app_name": settings.APP_NAME,
                            "first_name": user.first_name or "there",
                            "event": "Password changed",
                            "message": "Your password was changed successfully.",
                            "security_note": "If you did not perform this action, please contact support immediately.",
                        },
                        recipients=[user.email],
                        text_fallback=(
                            f"Hi {user.first_name or 'there'},\n\n"
                            "Your password was changed successfully.\n\n"
                            "If you did not perform this action, please contact support immediately."
                        ),
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Failed to send password change success email",
                        extra={"user_id": str(user.id), "email": user.email},
                    )

            transaction.on_commit(_send_confirmation)

        return {"changed": True}
