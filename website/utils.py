from django.http import Http404
from schools.models import School


def get_school_by_code_or_404(code: str) -> School:
    try:
        return School.objects.get(code=code, is_active=True)
    except School.DoesNotExist:
        raise Http404("School not found.")