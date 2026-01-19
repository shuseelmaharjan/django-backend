from django.contrib.auth import authenticate
from rest_framework import serializers
from accounts.models import User
from authx.models import UserSession
from utils.phone_utils import normalize_phone_for_login
from common.constants import UserStatus
from utils.phone_utils import strip_dial_code

# ==========================================================
# Login (validation serializer – used by view logic)
# ==========================================================
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Phone number")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]

        # Normalize phone (ignore dial code issues)
        normalized_phone = normalize_phone_for_login(identifier)

        user = (
            User.objects.filter(phone=normalized_phone).first()
            or User.objects.filter(username__iexact=identifier).first()
            or User.objects.filter(email__iexact=identifier).first()
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials.")

        if not user.has_usable_password():
            raise serializers.ValidationError("Password not set for this account.")

        request = self.context.get("request")

        # IMPORTANT: authenticate with PHONE (USERNAME_FIELD)
        authed = authenticate(
            request=request,
            username=user.phone,
            password=password,
        )

        if not authed:
            raise serializers.ValidationError("Invalid credentials.")

        if authed.status != UserStatus.ACTIVE:
            raise serializers.ValidationError(f"Account is {authed.status}.")

        attrs["user"] = authed
        return attrs


# ==========================================================
# Request serializers (Swagger / OpenAPI)
# ==========================================================
class LoginRequestSerializer(serializers.Serializer):
    """
    Swagger-visible request body for login
    """
    identifier = serializers.CharField(
        help_text="Email or phone number"
    )
    password = serializers.CharField(
        write_only=True,
        help_text="User password"
    )


# ==========================================================
# User serializers
# ==========================================================
class UserSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    role = serializers.CharField(source="get_role_display")

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "role",
            "status",
            "profile_picture_file",
        ]

    def get_phone(self, obj):
        return strip_dial_code(obj.phone)

    def get_name(self, obj):
        def clean(part: str) -> str:
            if not part:
                return ""
            part = part.strip()

            # Ignore placeholder / junk values
            if part.lower() in {"#", "# optional", "optional", "none", "null", "-"}:
                return ""

            return part

        parts = [
            clean(obj.first_name),
            clean(obj.middle_name),
            clean(obj.last_name),
        ]

        return " ".join(p for p in parts if p)


class MeSerializer(UserSerializer):
    """
    Backward compatibility alias
    """
    pass


# ==========================================================
# Response serializers (Swagger / OpenAPI)
# ==========================================================
class LoginResponseSerializer(serializers.Serializer):
    """
    Login response:
    - Web: refresh token is in HttpOnly cookie
    - Mobile: refreshToken is included in response
    """

    accessToken = serializers.CharField(
        help_text="JWT access token"
    )
    refreshToken = serializers.CharField(
        required=False,
        help_text="Only returned for mobile clients"
    )
    user = UserSerializer()


class RefreshResponseSerializer(serializers.Serializer):
    """
    Refresh token response
    """

    accessToken = serializers.CharField(
        help_text="New JWT access token"
    )
    refreshToken = serializers.CharField(
        required=False,
        help_text="New refresh token (mobile only if rotated)"
    )


class MeResponseSerializer(serializers.Serializer):
    """
    /me response payload
    """

    user = UserSerializer()
    session = serializers.DictField(
        help_text="Server-side session info"
    )


class LogoutResponseSerializer(serializers.Serializer):
    """
    Logout response
    """

    detail = serializers.CharField()

class UserSessionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id",
            "client_type",
            "device_id",
            "device_name",
            "os_name",
            "os_version",
            "app_version",
            "ip_address",
            "user_agent",
            "created_at",
            "last_seen_at",
            "revoked_at",
            "refresh_expires_at",
            "is_active",
            "is_current",
        ]

    def get_is_active(self, obj) -> bool:
        return bool(obj.is_active)

    def get_is_current(self, obj) -> bool:
        """
        The view will pass current_sid in serializer context.
        """
        current_sid = self.context.get("current_sid")
        return bool(current_sid and str(obj.id) == str(current_sid))


class SessionListResponseSerializer(serializers.Serializer):
    """
    Swagger response schema:
    """
    sessions = UserSessionSerializer(many=True)


class RevokeSessionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    revoked_session_id = serializers.UUIDField(required=False)
