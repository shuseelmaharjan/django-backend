from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework import exceptions

from authx.models import UserSession
from authx.utils import read_refresh_token


class JWTOrRefreshAuthentication(JWTAuthentication):
    """
    1) Try normal access-token auth
       - ALSO validate server-side session via sid claim
    2) If missing/expired, try refresh token
       - Validate session
       - Issue new access and attach to request for middleware
    """

    def _ensure_session_active(self, sid: str):
        if not sid:
            raise exceptions.AuthenticationFailed("Session missing. Please login again.")

        session = UserSession.objects.filter(id=sid).first()
        if not session or not session.is_active:
            raise exceptions.AuthenticationFailed("Session expired or revoked. Please login again.")

        session.touch()
        return session

    def authenticate(self, request):
        # ---- 1) Access token path ----
        try:
            result = super().authenticate(request)
            if result is not None:
                user, token = result  # token is the validated access token object
                sid = str(token.get("sid", ""))
                self._ensure_session_active(sid)
                return (user, token)
        except (InvalidToken, TokenError):
            # access token invalid/expired -> try refresh
            pass

        # ---- 2) Refresh fallback path ----
        refresh_str = read_refresh_token(request)
        if not refresh_str:
            return None

        try:
            refresh = RefreshToken(refresh_str)
            sid = str(refresh.get("sid", ""))
            self._ensure_session_active(sid)

            user = self.get_user(refresh)
            new_access = refresh.access_token
            new_access["sid"] = sid  # keep binding
            request._authx_new_access = str(new_access)

            return (user, None)
        except exceptions.AuthenticationFailed:
            raise
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid refresh token.")
