from rest_framework import permissions


def _token_role(token):
    payload = getattr(token, "payload", token)
    if hasattr(payload, "get"):
        return payload.get("role") or payload.get("role_type")
    return None


def is_admin_user(user, token=None):
    return bool(
        _token_role(token) == "admin"
        or (
            user
            and user.is_authenticated
            and (
                getattr(user, "role_type", None) == "admin"
                or getattr(user, "role", None) == "admin"
                or getattr(user, "is_staff", False)
                or getattr(user, "is_superuser", False)
            )
        )
    )


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_admin_user(request.user, request.auth)


class IsAdminOrSelf(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return bool(
            request.user and (request.user.is_staff or request.user.pk == obj.pk)
        )
