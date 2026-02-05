"""
Utility to get the active school for a user without importing models at module import time
(which can cause AppRegistryNotReady during Django startup).
"""

from typing import TYPE_CHECKING
from rest_framework.exceptions import ValidationError

if TYPE_CHECKING:
    # For type checkers only; avoids importing models at runtime during module import
    from schools.models import School


def get_school_for_user(user) -> "School":
    """
    Returns the active school owned by the user (school admin).
    Raise ValidationError if not found.
    This does a local import of the School model to avoid AppRegistryNotReady
    when this module is imported early during Django startup.
    """
    # Local import to avoid importing Django models at module import time
    from schools.models import School

    school = School.objects.filter(owner=user, is_active=True).first()
    if not school:
        raise ValidationError({"school": ["No active school found for this user."]})
    return school
