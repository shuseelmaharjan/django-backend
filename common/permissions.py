from rest_framework.permissions import BasePermission


class IsSuperUser(BasePermission):
    message = "Only superusers can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
