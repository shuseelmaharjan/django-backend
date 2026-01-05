import json

class AttachNewAccessTokenMiddleware:
    """
    If authentication created a new access token via refresh,
    attach it to every response:
      - header: X-Access-Token
      - body: add "accessToken" for JSON responses (best effort)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        new_access = getattr(request, "_authx_new_access", None)
        if not new_access:
            return response

        # header always
        response["X-Access-Token"] = new_access

        # body only if JSON and response is not streaming
        ctype = (response.get("Content-Type") or "").lower()
        if "application/json" in ctype and hasattr(response, "content"):
            try:
                payload = json.loads(response.content.decode("utf-8") or "{}")
                if isinstance(payload, dict) and "accessToken" not in payload:
                    payload["accessToken"] = new_access
                    response.content = json.dumps(payload).encode("utf-8")
                    response["Content-Length"] = str(len(response.content))
            except Exception:
                pass

        return response
