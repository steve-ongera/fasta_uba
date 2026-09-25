"""
api/permissions.py
Custom DRF permission classes shared across views.py.
"""

from rest_framework.permissions import BasePermission

from .models import Trip, User


class IsRider(BasePermission):
    message = "Only riders can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.RIDER)


class IsDriver(BasePermission):
    message = "Only drivers can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.DRIVER)


class IsTripParticipant(BasePermission):
    """Object-level permission: only the trip's rider or matched driver may access it."""
    message = "You are not a participant in this trip."

    def has_object_permission(self, request, view, obj: Trip):
        user = request.user
        if obj.rider_id == user.id:
            return True
        if obj.driver and obj.driver.user_id == user.id:
            return True
        return False


class IsOwner(BasePermission):
    """Generic 'obj.user == request.user' check for profile-style resources."""

    def has_object_permission(self, request, view, obj):
        return getattr(obj, "user_id", None) == request.user.id