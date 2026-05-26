from rest_framework import permissions


class CanViewWorkflow(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return (
            obj.created_by_id == request.user.id
            or obj.assigned_to_id == request.user.id
        )


class CanEditWorkflow(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.created_by_id == request.user.id
