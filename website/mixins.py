from rest_framework.exceptions import NotFound
from schools.models import School


class SchoolCodeMixin:
    school_lookup_kwarg = "school_code"

    def get_school(self):
        code = self.kwargs.get(self.school_lookup_kwarg)
        if not code:
            raise NotFound("School code is required.")

        try:
            return School.objects.get(code=code, is_active=True)
        except School.DoesNotExist:
            raise NotFound("School not found.")