from rest_framework import authentication, exceptions

from shared.auth.jwt_validator import validate_jwt


class ServiceUser:
    def __init__(self, user_id: int, role: str = "submitter"):
        self.id = user_id
        self.pk = user_id
        self.role = role

    @property
    def is_authenticated(self) -> bool:
        return True


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
