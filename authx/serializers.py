from django.contrib.auth import authenticate
from rest_framework import serializers
from accounts.models import User
from authx.models import UserSession


# ==========================================================
# Login (validation serializer – used by view logic)
# ==========================================================
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Email or phone number")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]

        # Try email/phone/username lookup (more robust)
        user = (
            User.objects.filter(email__iexact=identifier).first()
            or User.objects.filter(phone=identifier).first()
            or User.objects.filter(username__iexact=identifier).first()
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials.")

        # IMPORTANT: pass request + authenticate using the identifier the backend expects
        request = self.context.get("request")

        # If your USERNAME_FIELD is email, this works with ModelBackend:
        authed = authenticate(request=request, username=user.email, password=password)

        if not authed:
            # This means: password mismatch OR backend isn't configured to authenticate this user model
            raise serializers.ValidationError("Invalid credentials.")

        # Optional status check
        if hasattr(authed, "status") and str(authed.status).lower() != "active":
            raise serializers.ValidationError("User account is inactive.")

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
    """
    Canonical user payload returned by auth APIs
    """

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
        ]


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
