from common.school import get_school_id_from_request

class SchoolContextMiddleware:
    """
    If X-School-Id is present, set request.school_id (no validation here).
    Some viewsets still enforce required=True via SchoolScopedModelViewSet.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            request.school_id = get_school_id_from_request(request, required=False)
        except Exception:
            request.school_id = None
        return self.get_response(request)

class SchoolContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.school_id = get_school_id_from_request(request, required=False)
        return self.get_response(request)