import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.models import User, EmailChangeOTP
from accounts.utils import generate_numeric_otp, hash_otp, verify_otp
from filehandler.models import UploadedFile
from filehandler.serializers import UploadedFileSerializer
from smtp.services import send_html_template_email, send_email_change_success_notifications

from django.conf import settings
logger = logging.getLogger(__name__)

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the currently authenticated user's profile.
    """

    profile_picture_file = UploadedFileSerializer(
        read_only=True,
        context={},
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "email",
            "first_name",
            "middle_name",
            "last_name",
            "role",
            "status",
            "profile_picture_file",
            "username",
            "registration_no",
            "date_joined",
        ]
        read_only_fields = fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        field = self.fields.get("profile_picture_file")

        if field:
            field.context.update({"request": request})


class UserBasicInfoUpdateSerializer(serializers.ModelSerializer):
    """
    Updates the user's basic profile information.

    Email, role, status, username, registration number, and profile picture
    are intentionally excluded.
    """

    class Meta:
        model = User
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "phone",
        ]
        extra_kwargs = {
            "first_name": {
                "required": False,
                "allow_blank": True,
                "max_length": 150,
            },
            "middle_name": {
                "required": False,
                "allow_blank": True,
                "max_length": 80,
            },
            "last_name": {
                "required": False,
                "allow_blank": True,
                "max_length": 150,
            },
            "phone": {
                "required": False,
                "allow_blank": False,
            },
        }

    def validate_phone(self, value):
        try:
            from utils.phone_validator import clean_and_validate_phone

            value = clean_and_validate_phone(value)
        except serializers.ValidationError:
            raise
        except Exception:
            value = str(value).strip()

        if not value:
            raise serializers.ValidationError("Phone number is required.")

        user = self.instance

        exists = User.objects.filter(
            phone=value,
            is_deleted=False,
        ).exclude(pk=user.pk).exists()

        if exists:
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )

        return value

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one profile field must be provided."
            )

        return attrs

    def update(self, instance, validated_data):
        update_fields = []

        for field, value in validated_data.items():
            setattr(instance, field, value)
            update_fields.append(field)

        if update_fields:
            instance.save(update_fields=update_fields)

        return instance


class ProfilePictureUpdateSerializer(serializers.Serializer):
    """
    Associates an already-uploaded file with the current user's profile.

    The client should first upload the image through filehandler, then submit
    the returned UploadedFile UUID here.
    """

    profile_picture_file = serializers.PrimaryKeyRelatedField(
        queryset=UploadedFile.objects.all(),
        required=True,
        allow_null=False,
    )

    def validate_profile_picture_file(self, uploaded_file):
        request = self.context["request"]
        user = request.user

        if uploaded_file.uploaded_by_id not in (None, user.id):
            if not user.is_staff and not user.is_superuser:
                raise serializers.ValidationError(
                    "You cannot use a file uploaded by another user."
                )

        # Adjust this validation if FileType uses another image value.
        if uploaded_file.file_type not in ["image", "IMAGE"]:
            raise serializers.ValidationError(
                "The selected file must be an image."
            )

        if not uploaded_file.file:
            raise serializers.ValidationError(
                "The selected file is unavailable."
            )

        return uploaded_file

    @transaction.atomic
    def update(self, instance, validated_data):
        new_file = validated_data["profile_picture_file"]
        old_file = instance.profile_picture_file

        instance.profile_picture_file = new_file
        instance.save(update_fields=["profile_picture_file"])

        update_fields = []

        if new_file.is_temporary:
            new_file.is_temporary = False
            update_fields.append("is_temporary")

        if new_file.uploaded_by_id is None:
            new_file.uploaded_by = instance
            update_fields.append("uploaded_by")

        if update_fields:
            new_file.save(update_fields=update_fields)

        # The old file is not automatically deleted because it may be used
        # somewhere else. It can be removed explicitly through filehandler.
        return instance


class ProfilePictureRemoveSerializer(serializers.Serializer):
    """
    Removes the profile-picture relationship without deleting the file.
    """

    def update(self, instance, validated_data):
        instance.profile_picture_file = None
        instance.save(update_fields=["profile_picture_file"])
        return instance


class EmailChangeSendOTPSerializer(serializers.Serializer):
    """
    Starts an email change.

    The verification OTP is sent to the user's existing email address.
    """

    new_email = serializers.EmailField()

    def validate_new_email(self, value):
        value = value.strip().lower()
        request = self.context["request"]
        user = request.user

        if not user.email:
            raise serializers.ValidationError(
                "Your account does not have an existing email address. "
                "Contact support to add an email securely."
            )

        if value == user.email.strip().lower():
            raise serializers.ValidationError(
                "The new email must be different from the current email."
            )

        exists = User.objects.filter(
            email__iexact=value,
            is_deleted=False,
        ).exclude(pk=user.pk).exists()

        if exists:
            raise serializers.ValidationError(
                "This email address is already in use."
            )

        return value

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        current_email = user.email.strip().lower()
        new_email = validated_data["new_email"]

        otp = generate_numeric_otp()

        with transaction.atomic():
            # Invalidate previous unfinished requests.
            EmailChangeOTP.objects.filter(
                user=user,
                is_used=False,
            ).update(is_used=True)

            otp_obj = EmailChangeOTP.objects.create(
                user=user,
                current_email=current_email,
                new_email=new_email,
                otp_hash="",
                expires_at=EmailChangeOTP.default_expiry(),
            )

            otp_obj.otp_hash = hash_otp(
                otp,
                salt=str(otp_obj.id),
            )
            otp_obj.save(update_fields=["otp_hash"])

            subject = f"{settings.APP_NAME} email change verification"

            context = {
                "app_name": settings.APP_NAME,
                "first_name": user.first_name or "there",
                "otp": otp,
                "current_email": current_email,
                "new_email": new_email,
                "expires_minutes": 10,
            }

            text_fallback = (
                f"Hi {context['first_name']},\n\n"
                f"We received a request to change your email address "
                f"from {current_email} to {new_email}.\n\n"
                f"Your verification OTP is: {otp}\n"
                f"It expires in 10 minutes.\n\n"
                f"If you did not request this change, please secure your account "
                f"and contact support."
            )

            def _safe_send():
                try:
                    send_html_template_email(
                        subject=subject,
                        template_name="smtp/email_change_otp.html",
                        context=context,
                        recipients=[current_email],
                        text_fallback=text_fallback,
                    )
                except Exception:
                    import logging

                    logging.getLogger(__name__).exception(
                        "Failed to send email change OTP",
                        extra={
                            "user_id": str(user.id),
                            "current_email": current_email,
                            "new_email": new_email,
                        },
                    )

            transaction.on_commit(_safe_send)

        return {
            "sent": True,
            "current_email": current_email,
            "new_email": new_email,
        }


class EmailChangeVerifyOTPSerializer(serializers.Serializer):
    """
    Verifies the email-change OTP, updates the user's email address,
    invalidates remaining OTP requests, and sends confirmation emails
    to both the previous and new email addresses.
    """

    new_email = serializers.EmailField()

    otp = serializers.CharField(
        min_length=4,
        max_length=10,
        trim_whitespace=True,
    )

    def validate_new_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        new_email = attrs["new_email"]
        otp = attrs["otp"].strip()

        with transaction.atomic():
            otp_obj = (
                EmailChangeOTP.objects.select_for_update()
                .filter(
                    user=user,
                    new_email__iexact=new_email,
                    is_used=False,
                    expires_at__gt=timezone.now(),
                )
                .order_by("-created_at")
                .first()
            )

            if not otp_obj:
                raise serializers.ValidationError({
                    "otp": "Invalid or expired OTP."
                })

            current_user_email = (user.email or "").strip().lower()
            otp_current_email = (
                otp_obj.current_email or ""
            ).strip().lower()

            if otp_current_email != current_user_email:
                otp_obj.is_used = True
                otp_obj.save(update_fields=["is_used"])

                raise serializers.ValidationError({
                    "otp": (
                        "The account email changed after this OTP was issued. "
                        "Please request a new OTP."
                    )
                })

            if otp_obj.attempts >= otp_obj.max_attempts:
                otp_obj.is_used = True
                otp_obj.save(update_fields=["is_used"])

                raise serializers.ValidationError({
                    "otp": "Too many attempts. Please request a new OTP."
                })

            otp_is_valid = verify_otp(
                otp,
                otp_obj.otp_hash,
                salt=str(otp_obj.id),
            )

            otp_obj.attempts += 1

            if not otp_is_valid:
                update_fields = ["attempts"]

                if otp_obj.attempts >= otp_obj.max_attempts:
                    otp_obj.is_used = True
                    update_fields.append("is_used")

                otp_obj.save(update_fields=update_fields)

                raise serializers.ValidationError({
                    "otp": "Invalid or expired OTP."
                })

            email_exists = (
                User.objects.filter(
                    email__iexact=new_email,
                    is_deleted=False,
                )
                .exclude(pk=user.pk)
                .exists()
            )

            if email_exists:
                otp_obj.is_used = True
                otp_obj.save(update_fields=["is_used"])

                raise serializers.ValidationError({
                    "new_email": "This email address is already in use."
                })

            otp_obj.verified_at = timezone.now()

            attrs["_otp_obj_id"] = otp_obj.pk

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        request_user = request.user

        new_email = validated_data["new_email"]
        otp_obj_id = validated_data["_otp_obj_id"]

        with transaction.atomic():
            # Lock the user row so concurrent account updates cannot conflict.
            user = (
                User.objects.select_for_update()
                .get(pk=request_user.pk)
            )

            # Lock and reload the OTP because validate() and create() may run
            # in separate database transactions.
            otp_obj = (
                EmailChangeOTP.objects.select_for_update()
                .filter(
                    pk=otp_obj_id,
                    user=user,
                    new_email__iexact=new_email,
                    is_used=False,
                )
                .first()
            )

            if not otp_obj:
                raise serializers.ValidationError({
                    "otp": (
                        "This verification request is no longer valid. "
                        "Please request a new OTP."
                    )
                })

            if otp_obj.expires_at <= timezone.now():
                otp_obj.is_used = True
                otp_obj.save(update_fields=["is_used"])

                raise serializers.ValidationError({
                    "otp": "Invalid or expired OTP."
                })

            old_email = (user.email or "").strip().lower()
            otp_current_email = (
                otp_obj.current_email or ""
            ).strip().lower()

            if old_email != otp_current_email:
                otp_obj.is_used = True
                otp_obj.save(update_fields=["is_used"])

                raise serializers.ValidationError({
                    "email": (
                        "The current account email no longer matches this "
                        "verification request. Please request a new OTP."
                    )
                })

            email_exists = (
                User.objects.filter(
                    email__iexact=new_email,
                    is_deleted=False,
                )
                .exclude(pk=user.pk)
                .exists()
            )

            if email_exists:
                otp_obj.is_used = True
                otp_obj.save(update_fields=["is_used"])

                raise serializers.ValidationError({
                    "new_email": "This email address is already in use."
                })

            user.email = new_email
            user.save(update_fields=["email"])

            otp_obj.is_used = True
            otp_obj.verified_at = (
                otp_obj.verified_at or timezone.now()
            )
            otp_obj.save(
                update_fields=[
                    "is_used",
                    "verified_at",
                ]
            )

            # Invalidate every remaining unused email-change OTP.
            EmailChangeOTP.objects.filter(
                user=user,
                is_used=False,
            ).exclude(
                pk=otp_obj.pk,
            ).update(
                is_used=True,
            )

            user_id = str(user.pk)
            first_name = user.first_name or "there"
            app_name = getattr(
                settings,
                "APP_NAME",
                "Application",
            )

            def _send_confirmations():
                self._send_old_email_confirmation(
                    user_id=user_id,
                    first_name=first_name,
                    app_name=app_name,
                    old_email=old_email,
                    new_email=new_email,
                )

                self._send_new_email_confirmation(
                    user_id=user_id,
                    first_name=first_name,
                    app_name=app_name,
                    old_email=old_email,
                    new_email=new_email,
                )

            transaction.on_commit(_send_confirmations)

        return {
            "changed": True,
            "old_email": old_email,
            "new_email": new_email,
        }

    @staticmethod
    def _send_old_email_confirmation(
        *,
        user_id: str,
        first_name: str,
        app_name: str,
        old_email: str,
        new_email: str,
    ):
        """
        Notify the previous email address that the account email
        was successfully changed.
        """

        if not old_email:
            return

        try:
            send_html_template_email(
                subject=f"Your {app_name} email address was changed",
                template_name="smtp/email_change_success.html",
                context={
                    "app_name": app_name,
                    "first_name": first_name,
                    "old_email": old_email,
                    "new_email": new_email,
                    "notification_type": "old_email",
                },
                recipients=[old_email],
                text_fallback=(
                    f"Hi {first_name},\n\n"
                    f"The email address associated with your "
                    f"{app_name} account was changed successfully.\n\n"
                    f"Previous email: {old_email}\n"
                    f"New email: {new_email}\n\n"
                    f"If you did not perform this action, contact "
                    f"support immediately and secure your account."
                ),
            )

        except Exception:
            logger.exception(
                "Failed to send email-change notification to old email",
                extra={
                    "user_id": user_id,
                    "old_email": old_email,
                    "new_email": new_email,
                },
            )

    @staticmethod
    def _send_new_email_confirmation(
        *,
        user_id: str,
        first_name: str,
        app_name: str,
        old_email: str,
        new_email: str,
    ):
        """
        Notify the new email address that it is now associated
        with the user's account.
        """

        if not new_email:
            return

        try:
            send_html_template_email(
                subject=f"Your new {app_name} email is confirmed",
                template_name="smtp/email_change_success.html",
                context={
                    "app_name": app_name,
                    "first_name": first_name,
                    "old_email": old_email,
                    "new_email": new_email,
                    "notification_type": "new_email",
                },
                recipients=[new_email],
                text_fallback=(
                    f"Hi {first_name},\n\n"
                    f"Your email address was updated successfully.\n\n"
                    f"{new_email} is now connected to your "
                    f"{app_name} account.\n\n"
                    f"You can now use this email address to sign in "
                    f"and receive account notifications.\n\n"
                    f"If you did not perform this action, contact "
                    f"support immediately."
                ),
            )

        except Exception:
            logger.exception(
                "Failed to send email-change confirmation to new email",
                extra={
                    "user_id": user_id,
                    "old_email": old_email,
                    "new_email": new_email,
                },
            )