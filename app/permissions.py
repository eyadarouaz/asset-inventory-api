from rest_framework.permissions import BasePermission

from .models import Role


class IsAdminOnly(BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.ADMIN
        )


class IsAdminOrReadOnly(BasePermission):
    """
    Allow full access only to admins.
    """

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True

        # For modifying methods, user must be admin
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.ADMIN
        )
