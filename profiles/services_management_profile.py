from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from accounts.models import User
from profiles.models import Profile


def get_management_school(user):
    """
    Resolve the school managed by the authenticated user.

    Adjust this function if your management user uses another relation,
    such as user.school, user.staff_profile.school, or memberships.
    """

    if user.is_superuser:
        return None

    try:
        return user.profile.school
    except Profile.DoesNotExist:
        raise ValidationError({
            "school": (
                "The authenticated management user is not associated "
                "with a school."
            )
        })


def get_managed_user_or_404(request, user_id):
    """
    Prevent school management users from accessing users belonging
    to another school.
    """

    queryset = User.objects.filter(
        pk=user_id,
        is_deleted=False,
    ).select_related(
        "profile",
        "profile__school",
        "profile_picture_file",
    )

    if not request.user.is_superuser:
        school = get_management_school(request.user)
        queryset = queryset.filter(profile__school=school)

    return get_object_or_404(queryset)


def get_or_create_managed_profile(request, target_user):
    """
    Returns the target user's profile.

    A new profile is only created if the authenticated manager's school
    can be resolved.
    """

    try:
        return target_user.profile
    except Profile.DoesNotExist:
        school = get_management_school(request.user)

        if school is None:
            raise ValidationError({
                "school": (
                    "A school is required to create this user's profile."
                )
            })

        return Profile.objects.create(
            school=school,
            user=target_user,
        )