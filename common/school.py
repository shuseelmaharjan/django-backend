from dataclasses import dataclass
from rest_framework import exceptions

SCHOOL_HEADER = "HTTP_X_SCHOOL_ID"  # Django converts X-School-Id -> HTTP_X_SCHOOL_ID

@dataclass(frozen=True)
class SchoolContext:
    school_id: str

def get_school_id_from_request(request, required: bool = True) -> str | None:
    school_id = (request.META.get(SCHOOL_HEADER) or "").strip()
    if not school_id and required:
        raise exceptions.ValidationError({"schoolId": "Missing X-School-Id header."})
    return school_id or None

def get_school_context(request, required: bool = True) -> SchoolContext | None:
    school_id = get_school_id_from_request(request, required=required)
    return SchoolContext(school_id=school_id) if school_id else None
