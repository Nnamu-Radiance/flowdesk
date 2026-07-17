from rest_framework import permissions

INSTITUTIONAL_APPROVER_ROLES = {
    "admin_assistant",
    "administrative_assistant",
    "dean",
    "deputy_vice_chancellor",
    "dvc",
    "faculty_council",
    "faculty_scientific_council",
    "head_of_department",
    "hod",
    "registrar",
    "supervisor",
}


def normalized_role(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("/", "_")


def user_is_approver(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    roles = {
        normalized_role(getattr(user, "role", "")),
        normalized_role(getattr(user, "approver_type", "")),
    }
    return bool(roles & ({"admin", "approver"} | INSTITUTIONAL_APPROVER_ROLES))


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")


class IsApprover(permissions.BasePermission):
    def has_permission(self, request, view):
        return user_is_approver(request.user)


class IsSubmitter(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "submitter")
