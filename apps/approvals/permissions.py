from rest_framework import permissions


class CanApprove(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return bool(
            request.user
            and (request.user.is_staff or obj.assigned_to_id == request.user.id)
        )
