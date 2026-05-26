import os
from typing import Any

import jwt
from django.core.exceptions import PermissionDenied


def validate_jwt(token: str) -> dict[str, Any]:
    """Validate JWT locally using shared secret."""
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise PermissionDenied("JWT secret not configured")

    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise PermissionDenied("Invalid token") from exc
