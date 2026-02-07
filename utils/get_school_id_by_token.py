"""
Get school for the user.
- Superadmin may not have a school -> raise ValidationError (or handle separately).
- School admin (owner) -> School.owner
- Other roles -> Profile.school
"""

from typing import TYPE_CHECKING
from rest_framework.exceptions import ValidationError

if TYPE_CHECKING:
    from schools.models import School


def get_school_for_user(user) -> "School":
    from schools.models import School
    from profiles.models import Profile

    # 1) Owner-based school (your current logic)
    school = School.objects.filter(owner=user, is_active=True).first()
    if school:
        return school

    # 2) Profile-based school (staff/teachers/etc.)
    profile = Profile.objects.select_related("school").filter(user=user).first()
    if profile and profile.school and profile.school.is_active:
        return profile.school

    raise ValidationError({"school": ["No active school found for this user."]})
