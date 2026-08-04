from __future__ import annotations

from rest_framework.permissions import BasePermission

from common.constants import UserRole


def _allowed(request, roles):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, "role", None) in roles


class CanViewFeeManagement(BasePermission):
    message = "You do not have permission to view financial records."
    roles = (
        UserRole.PRINCIPAL,
        UserRole.ADMIN,
        UserRole.VICE_PRINCIPAL,
        UserRole.ACCOUNTANT,
        UserRole.CASHIER,
        UserRole.ADMISSIONS,
        UserRole.REGISTRAR,
    )

    def has_permission(self, request, view):
        return _allowed(request, self.roles)


class CanPostFeePayments(BasePermission):
    message = "Only school administrators or finance staff can post payments."
    roles = (
        UserRole.PRINCIPAL,
        UserRole.ADMIN,
        UserRole.VICE_PRINCIPAL,
        UserRole.ACCOUNTANT,
        UserRole.CASHIER,
    )

    def has_permission(self, request, view):
        return _allowed(request, self.roles)


class CanManageFeeConcessions(BasePermission):
    message = "Only authorized administrators or accountants can manage concessions."
    roles = (
        UserRole.PRINCIPAL,
        UserRole.ADMIN,
        UserRole.VICE_PRINCIPAL,
        UserRole.ACCOUNTANT,
    )

    def has_permission(self, request, view):
        return _allowed(request, self.roles)


class CanReverseFinancialDocuments(BasePermission):
    message = "Only principals, administrators, or accountants can reverse financial documents."
    roles = (
        UserRole.PRINCIPAL,
        UserRole.ADMIN,
        UserRole.ACCOUNTANT,
    )

    def has_permission(self, request, view):
        return _allowed(request, self.roles)
