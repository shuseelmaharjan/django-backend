# common/schema.py
from drf_spectacular.utils import extend_schema, OpenApiResponse

DEFAULT_400 = OpenApiResponse(description="Bad request")

def schema(
    *,
    tag: str,
    summary: str,
    request=None,
    responses=None,
    **kwargs,
):
    final_responses = dict(responses or {})
    final_responses.setdefault(400, DEFAULT_400)

    return extend_schema(
        tags=[tag],
        summary=summary,
        request=request,
        responses=final_responses,
        **kwargs,
    )
