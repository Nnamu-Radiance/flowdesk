from django.core.cache import cache
from django.db import connection
from rest_framework import permissions, response, status, views
from rest_framework.decorators import api_view, permission_classes

from apps.notifications.models import Notification


def serialize_notification(notification):
    return {
        "id": notification.id,
        "type": notification.type,
        "message": notification.message,
        "is_read": notification.read,
        "created_at": notification.created_at.isoformat(),
        "workflow_id": notification.workflow_id,
    }


class NotificationListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(recipient_id=request.user.id).order_by("read", "-created_at")[:50]
        return response.Response([serialize_notification(item) for item in notifications])


class NotificationReadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk: int):
        updated = Notification.objects.filter(pk=pk, recipient_id=request.user.id).update(read=True)
        if not updated:
            return response.Response({"detail": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)
        return response.Response({"id": pk, "is_read": True})


class NotificationReadAllView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(recipient_id=request.user.id, read=False).update(read=True)
        return response.Response({"updated": count})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    checks = {"database": "error", "cache": "error"}
    details = {}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception as exc:
        details["database"] = str(exc)

    try:
        cache.set("health", "ok", 10)
        checks["cache"] = "ok"
    except Exception as exc:
        details["cache"] = str(exc)

    healthy = all(value == "ok" for value in checks.values())
    payload = {"status": "healthy" if healthy else "unhealthy", **checks}
    if details:
        payload["details"] = details
    return response.Response(
        payload,
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
