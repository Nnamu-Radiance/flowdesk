from rest_framework import authentication, exceptions

from apps.approvals.service_user import ServiceUser
from shared.auth.jwt_validator import validate_jwt


class JWTLocalAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None

        token = auth.split(" ", 1)[1].strip()
        try:
            payload = validate_jwt(token)
        except Exception as exc:
            raise exceptions.AuthenticationFailed("Invalid JWT") from exc

        user = ServiceUser(payload.get("user_id") or payload.get("id"), payload.get("role", "submitter"))
        return user, payload
