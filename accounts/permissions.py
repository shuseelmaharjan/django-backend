from rest_framework import permissions
from django.utils import timezone
from accounts.models import RoleAssignment
from common.constants import ScopeType

def _has_role(user, role_code: str, school_id: str | None = None) -> bool:
    if not user or not user.is_authenticated:
        return False

    now = timezone.now()
    qs = RoleAssignment.objects.select_related("role").filter(user=user, role__code=role_code)

    # Global role always accepted
    qs_global = qs.filter(scope_type=ScopeType.GLOBAL)
    for ra in qs_global:
        if ra.is_active(at=now):
            return True

    if school_id:
        qs_school = qs.filter(scope_type=ScopeType.SCHOOL, scope_id=school_id)
        for ra in qs_school:
            if ra.is_active(at=now):
                return True

    return False


class IsSchoolAdmin(permissions.BasePermission):
    """
    Allows access if the user has 'admin' role in GLOBAL or SCHOOL scope for X-School-Id.
    """

    message = "Admin role required."

    def has_permission(self, request, view) -> bool:
        school_id = getattr(request, "school_id", None)
        return _has_role(request.user, "admin", school_id=school_id)


class IsAuthenticatedReadOnlyOrAdmin(permissions.BasePermission):
    """
    Read allowed for any authenticated user; write requires admin.
    """

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        school_id = getattr(request, "school_id", None)
        return _has_role(request.user, "admin", school_id=school_id)
