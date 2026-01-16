from django.db import transaction
from django.utils import timezone

from accounts.models import User, Role, RoleAssignment
from staff.models import StaffProfile
from common.constants import ScopeType, StaffType


@transaction.atomic
def ensure_school_roles(school_id: str):
    """
    Make sure base roles exist for this school.
    school_id should be str(UUID).
    """
    roles = [
        ("school_admin", "School Admin"),
        ("principal", "Principal"),
    ]

    created = []
    for code, name in roles:
        role, _ = Role.objects.get_or_create(
            school_id=school_id,
            code=code,
            defaults={"name": name, "is_system": True},
        )
        # if name changed, keep updated
        if role.name != name:
            role.name = name
            role.save(update_fields=["name"])
        created.append(role)

    return created


@transaction.atomic
def create_principal_user_for_school(
    *,
    school_id: str,
    email: str,
    password: str | None = None,
    username: str | None = None,
    phone: str = "",
    first_name: str = "",
    last_name: str = "",
    make_staff_profile: bool = True,
):
    """
    Creates:
      - accounts.User
      - staff.StaffProfile (optional) with staff_type=principal
      - RoleAssignment to principal role, scoped to SCHOOL + school_id
    """
    # 1) Ensure roles exist
    ensure_school_roles(school_id)
    principal_role = Role.objects.get(school_id=school_id, code="principal")

    # 2) Create user
    user = User.objects.create_user(
        email=email,
        password=password,
        username=username or email,
        phone=phone or "",
        first_name=first_name or "",
        last_name=last_name or "",
        status="active",
    )

    # 3) Create staff profile (principal)
    if make_staff_profile:
        StaffProfile.objects.create(
            user=user,
            school_id=school_id,
            staff_type=StaffType.PRINCIPAL,
            employment_status="active",
        )

    # 4) Assign principal role (school scoped)
    RoleAssignment.objects.get_or_create(
        user=user,
        role=principal_role,
        scope_type=ScopeType.SCHOOL,
        scope_id=school_id,
        defaults={"valid_from": timezone.now()},
    )

    return user
