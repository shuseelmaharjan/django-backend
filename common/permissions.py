from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS
from common.constants import UserRole


def _is_authed(request) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated)


def _is_platform_superadmin(request) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_superuser)


class IsPlatformSuperAdmin(BasePermission):
    """
    Platform (SaaS owner) superadmin only.
    Use for: create school, create principal, platform-wide settings, billing, etc.
    """
    message = "Only platform super admins can perform this action."

    def has_permission(self, request, view):
        return _is_platform_superadmin(request)


class HasAnyRole(BasePermission):
    """
    Base role permission (single-role per user).
    - Authenticated required
    - Platform superadmin bypass allowed
    """
    allowed_roles: tuple[str, ...] = ()
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        if not _is_authed(request):
            return False

        # platform superadmin bypass
        if _is_platform_superadmin(request):
            return True

        user = request.user
        return bool(user.role and user.role in self.allowed_roles)


class HasRole(HasAnyRole):
    """
    Same as HasAnyRole, but specify roles per-view:
      permission_classes = [HasRole]
      HasRole.allowed_roles = (UserRole.TEACHER, ...)
    """
    pass


# ---------- Common grouped permissions ----------

class IsSchoolAdmin(HasAnyRole):
    """
    Principal/Admin/Vice Principal
    """
    message = "Only school administrators can perform this action."
    allowed_roles = (
        UserRole.PRINCIPAL,
        UserRole.ADMIN,
        UserRole.VICE_PRINCIPAL,
    )


class IsPrincipal(HasAnyRole):
    message = "Only principals can perform this action."
    allowed_roles = (UserRole.PRINCIPAL,)


class IsAdmin(HasAnyRole):
    message = "Only admins can perform this action."
    allowed_roles = (UserRole.ADMIN,)


class IsVicePrincipal(HasAnyRole):
    message = "Only vice principals can perform this action."
    allowed_roles = (UserRole.VICE_PRINCIPAL,)


class IsTeacher(HasAnyRole):
    message = "Only teachers can perform this action."
    allowed_roles = (UserRole.TEACHER,)


class IsCoordinator(HasAnyRole):
    message = "Only coordinators can perform this action."
    allowed_roles = (UserRole.COORDINATOR,)


class IsAcademicStaff(HasAnyRole):
    """
    Teacher/Coordinator
    """
    message = "Only academic staff can perform this action."
    allowed_roles = (
        UserRole.TEACHER,
        UserRole.COORDINATOR,
    )


class IsFinanceStaff(HasAnyRole):
    """
    Accountant/Cashier
    """
    message = "Only finance staff can perform this action."
    allowed_roles = (
        UserRole.ACCOUNTANT,
        UserRole.CASHIER,
    )


class IsAccountant(HasAnyRole):
    message = "Only accountants can perform this action."
    allowed_roles = (UserRole.ACCOUNTANT,)


class IsCashier(HasAnyRole):
    message = "Only cashiers can perform this action."
    allowed_roles = (UserRole.CASHIER,)


class IsAdmissionsStaff(HasAnyRole):
    """
    Admissions/Registrar
    """
    message = "Only admissions staff can perform this action."
    allowed_roles = (
        UserRole.ADMISSIONS,
        UserRole.REGISTRAR,
    )


class IsAdmissionsOfficer(HasAnyRole):
    message = "Only admissions officers can perform this action."
    allowed_roles = (UserRole.ADMISSIONS,)


class IsRegistrar(HasAnyRole):
    message = "Only registrars can perform this action."
    allowed_roles = (UserRole.REGISTRAR,)


class IsLibrarian(HasAnyRole):
    message = "Only librarians can perform this action."
    allowed_roles = (UserRole.LIBRARIAN,)


class IsTransportManager(HasAnyRole):
    message = "Only transport managers can perform this action."
    allowed_roles = (UserRole.TRANSPORT,)


class IsHostelWarden(HasAnyRole):
    message = "Only hostel/warden staff can perform this action."
    allowed_roles = (UserRole.HOSTEL,)


class IsITAdmin(HasAnyRole):
    message = "Only IT administrators can perform this action."
    allowed_roles = (UserRole.IT,)


class IsOperationsStaff(HasAnyRole):
    """
    Transport/Hostel/Librarian/IT
    """
    message = "Only operations staff can perform this action."
    allowed_roles = (
        UserRole.TRANSPORT,
        UserRole.HOSTEL,
        UserRole.LIBRARIAN,
        UserRole.IT,
    )


# ---------- Utility permission patterns ----------

class ReadOnly(BasePermission):
    """
    Allows read-only (SAFE_METHODS) for everyone (even unauthenticated).
    Combine with another permission in permission_classes if needed.
    """
    message = "Read-only endpoint."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class IsAuthenticatedAndActive(BasePermission):
    """
    Authenticated and status must be ACTIVE.
    Uses your enum: UserStatus.ACTIVE (string 'active').
    """
    message = "Your account is not active."

    def has_permission(self, request, view):
        if not _is_authed(request):
            return False
        return str(getattr(request.user, "status", "")).lower() == "active"


class IsSchoolAdminOrReadOnly(IsSchoolAdmin):
    """
    Read for all authenticated users, write only for school admins.
    """
    message = "Only school administrators can modify this resource."

    def has_permission(self, request, view):
        if not _is_authed(request):
            return False
        if request.method in SAFE_METHODS:
            return True
        return super().has_permission(request, view)


class IsFinanceStaffOrReadOnly(IsFinanceStaff):
    """
    Read for all authenticated users, write only for finance staff.
    """
    message = "Only finance staff can modify this resource."

    def has_permission(self, request, view):
        if not _is_authed(request):
            return False
        if request.method in SAFE_METHODS:
            return True
        return super().has_permission(request, view)
