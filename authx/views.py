# authx/views.py

from django.conf import settings
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiResponse,
)

from authx.models import UserSession
from authx.serializers import (
    # validation / output serializers you already have
    LoginSerializer,
    MeSerializer,
    # documentation serializers (add these in authx/serializers.py)
    LoginRequestSerializer,
    LoginResponseSerializer,
    RefreshResponseSerializer,
    MeResponseSerializer,
    LogoutResponseSerializer,
)
from authx.tokens import issue_tokens_and_session
from authx.utils import (
    get_client_type,
    read_refresh_token,
    set_refresh_cookie,
    clear_refresh_cookie,
)

# ---- Shared Swagger params ----
CLIENT_TYPE_HEADER = OpenApiParameter(
    name="X-Client-Type",
    type=str,
    location=OpenApiParameter.HEADER,
    required=False,
    description="Client type: web or mobile (default: web). Web stores refresh token in HttpOnly cookie; mobile gets refreshToken in JSON.",
)

REFRESH_HEADER = OpenApiParameter(
    name="X-Refresh-Token",
    type=str,
    location=OpenApiParameter.HEADER,
    required=False,
    description="Mobile clients can pass refresh token here. Web uses HttpOnly refresh cookie.",
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["01. Auth"],
        request=LoginRequestSerializer,
        parameters=[CLIENT_TYPE_HEADER],
    )
    def post(self, request):
        ser = LoginSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]

        # clear any stale refresh cookie
        resp = Response(status=status.HTTP_200_OK)
        clear_refresh_cookie(resp)

        access, refresh = issue_tokens_and_session(request, user)
        client_type = get_client_type(request)

        payload = {
            "accessToken": access,
            "user": MeSerializer(user).data,
        }

        resp.data = payload

        if client_type == "web":
            set_refresh_cookie(resp, refresh)
        else:
            payload["refreshToken"] = refresh

        resp["X-Access-Token"] = access
        return resp


class RefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["01. Auth"],
        parameters=[CLIENT_TYPE_HEADER, REFRESH_HEADER],
    )
    def post(self, request):
        token_str = read_refresh_token(request)
        if not token_str:
            return Response({"detail": "No refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(token_str)
        except TokenError:
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

        jti = str(refresh.get("jti", ""))

        # Session must exist and be active (server-side session tracking)
        session = (
            UserSession.objects.filter(refresh_jti=jti, revoked_at__isnull=True)
            .select_related("user")
            .first()
        )
        if not session or not session.is_active:
            return Response({"detail": "Session expired or revoked."}, status=status.HTTP_401_UNAUTHORIZED)

        # access can be generated from refresh
        try:
            new_access = str(refresh.access_token)
        except TokenError:
            return Response({"detail": "Refresh failed."}, status=status.HTTP_401_UNAUTHORIZED)

        rotate = getattr(settings, "SIMPLE_JWT", {}).get("ROTATE_REFRESH_TOKENS", False)
        if rotate:
            # revoke old session and issue brand-new refresh+access
            session.revoke()
            new_access, new_refresh_str = issue_tokens_and_session(request, session.user)
        else:
            new_refresh_str = token_str

        session.touch()

        client_type = get_client_type(request)
        payload = {"accessToken": new_access}

        resp = Response(payload, status=status.HTTP_200_OK)
        resp["X-Access-Token"] = new_access

        if client_type == "web":
            set_refresh_cookie(resp, new_refresh_str)
        else:
            payload["refreshToken"] = new_refresh_str
            resp.data = payload

        return resp


@extend_schema(tags=["01. Auth"])
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        token_str = read_refresh_token(request)

        session_active = False
        new_access = None

        if token_str:
            try:
                rt = RefreshToken(token_str)
                sid = str(rt.get("sid", ""))

                session = UserSession.objects.filter(id=sid, revoked_at__isnull=True).first()
                session_active = bool(session and session.is_active)

                if session_active:
                    # issue "current" access token
                    at = rt.access_token
                    at["sid"] = sid
                    new_access = str(at)
                    session.touch()
                else:
                    # refresh exists but session is dead -> treat as invalid credentials/session
                    resp = Response(
                        {"detail": "Session expired or revoked. Please login again."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                    clear_refresh_cookie(resp)
                    return resp

            except Exception:
                # refresh token broken -> unauthorized from session perspective
                resp = Response(
                    {"detail": "Invalid refresh token. Please login again."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
                clear_refresh_cookie(resp)
                return resp

        data = {
            "user": MeSerializer(user).data,
            "session": {
                "active": session_active,
                "serverTime": timezone.now(),
            },
        }

        if new_access:
            data["accessToken"] = new_access  # <-- required by you
        resp = Response(data, status=status.HTTP_200_OK)

        if new_access:
            resp["X-Access-Token"] = new_access

        # If web client and you want to keep refresh cookie refreshed, you can re-set it (optional)
        # client_type = get_client_type(request)
        # if client_type == "web" and token_str:
        #     set_refresh_cookie(resp, token_str)

        return resp

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["01. Auth"],
        parameters=[CLIENT_TYPE_HEADER, REFRESH_HEADER],
    )
    def post(self, request):
        token_str = read_refresh_token(request)
        if token_str:
            try:
                rt = RefreshToken(token_str)
                jti = str(rt.get("jti", ""))
                UserSession.objects.filter(refresh_jti=jti, revoked_at__isnull=True).update(
                    revoked_at=timezone.now()
                )
            except Exception:
                pass

        resp = Response({"detail": "Logged out"}, status=status.HTTP_200_OK)
        clear_refresh_cookie(resp)
        return resp
