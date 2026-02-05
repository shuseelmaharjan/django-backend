from django.conf import settings

def get_client_type(request) -> str:
    # Default web if not provided
    ct = (request.headers.get("X-Client-Type") or "web").strip().lower()
    return "mobile" if ct == "mobile" else "web"


def set_refresh_cookie(response, refresh_token: str):
    max_age = int(getattr(settings, "AUTHX_REFRESH_COOKIE_MAX_AGE", 0)) or None

    response.set_cookie(
        key=getattr(settings, "AUTHX_REFRESH_COOKIE_NAME", "refresh_token"),
        value=refresh_token,
        httponly=getattr(settings, "AUTHX_REFRESH_COOKIE_HTTPONLY", True),
        secure=getattr(settings, "AUTHX_REFRESH_COOKIE_SECURE", False),
        samesite=getattr(settings, "AUTHX_REFRESH_COOKIE_SAMESITE", "Lax"),
        path=getattr(settings, "AUTHX_REFRESH_COOKIE_PATH", "/"),
        max_age=max_age,  # this makes it NOT "Session"
    )


def clear_refresh_cookie(response):
    response.delete_cookie(
        key=getattr(settings, "AUTHX_REFRESH_COOKIE_NAME", "refresh_token"),
        path=getattr(settings, "AUTHX_REFRESH_COOKIE_PATH", "/"),
    )


def read_refresh_token(request) -> str | None:
    """
    Web: cookie refresh_token
    Mobile: allow header X-Refresh-Token (recommended)
    """
    cookie_name = getattr(settings, "AUTHX_REFRESH_COOKIE_NAME", "refresh_token")
    token = request.COOKIES.get(cookie_name)
    if token:
        return token
    # mobile/header fallback
    hdr = request.headers.get("X-Refresh-Token")
    if hdr:
        return hdr.strip()
    return None
