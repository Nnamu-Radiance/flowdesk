from django.core.cache import cache
from django.db import connection
from rest_framework import permissions, response, status, views
from rest_framework.decorators import api_view, permission_classes

from apps.analytics.services import AnalyticsService


class DashboardView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        def compute():
            return {
                "total_workflows": 0,
                "approved": 0,
                "rejected": 0,
                "pending": 0,
            }

        payload = AnalyticsService.cached_payload("analytics:dashboard", compute)
        return response.Response(payload)


class SLAReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        payload = AnalyticsService.cached_payload(
            "analytics:sla-report",
            lambda: {"compliance_rate": 100.0, "departments": []},
        )
        return response.Response(payload)


class WorkflowVolumeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        payload = AnalyticsService.cached_payload("analytics:volume", lambda: {"points": []})
        return response.Response(payload)


class ApproverPerformanceView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        payload = AnalyticsService.cached_payload("analytics:approver-performance", lambda: {"approvers": []})
        return response.Response(payload)


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
