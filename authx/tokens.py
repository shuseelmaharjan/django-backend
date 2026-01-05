import uuid
from datetime import datetime, UTC
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from authx.models import UserSession
from authx.utils import get_client_type


def get_client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def issue_tokens_and_session(request, user):
    client_type = get_client_type(request)

    session_id = uuid.uuid4()

    refresh = RefreshToken.for_user(user)
    refresh["sid"] = str(session_id)  # bind refresh to session

    access = refresh.access_token
    access["sid"] = str(session_id)   # bind access to same session

    refresh_jti = str(refresh["jti"])
    refresh_exp = datetime.fromtimestamp(refresh["exp"], tz=UTC)

    UserSession.objects.create(
        id=session_id,
        user=user,
        client_type=client_type,
        refresh_jti=refresh_jti,
        refresh_expires_at=refresh_exp,
        device_id=request.headers.get("X-Device-ID", ""),
        device_name=request.headers.get("X-Device-Name", ""),
        os_name=request.headers.get("X-OS-Name", ""),
        os_version=request.headers.get("X-OS-Version", ""),
        app_version=request.headers.get("X-App-Version", ""),
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        last_seen_at=timezone.now(),
    )

    return str(access), str(refresh)
