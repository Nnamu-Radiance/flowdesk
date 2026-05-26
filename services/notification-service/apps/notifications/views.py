from django.core.cache import cache
from django.db import connection
from rest_framework import permissions, response, status
from rest_framework.decorators import api_view, permission_classes


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    checks = {"database": "error", "cache": "error"}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        pass

    try:
        cache.set("health", "ok", 10)
        checks["cache"] = "ok"
    except Exception:
        pass

    healthy = all(value == "ok" for value in checks.values())
    return response.Response(
        {"status": "healthy" if healthy else "unhealthy", **checks},
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
