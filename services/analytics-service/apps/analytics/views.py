from django.core.cache import cache
from django.db import connection
from rest_framework import permissions, response, status, views
from rest_framework.decorators import api_view, permission_classes

from apps.analytics.services import AnalyticsService


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, "role", "") == "admin")


def dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def scalar(sql: str, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        row = cursor.fetchone()
    return row[0] if row else 0


def rows(sql: str, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return dictfetchall(cursor)


class DashboardView(views.APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        def compute():
            total = scalar("select count(*) from workflow_svc.workflows_workflow")
            pending = scalar(
                "select count(*) from workflow_svc.workflows_workflow "
                "where status in ('submitted', 'in_approval')"
            )
            approved_month = scalar(
                "select count(*) from approval_svc.approvals_approvalchain "
                "where status = 'approved' and created_at >= date_trunc('month', now())"
            )
            rejected_month = scalar(
                "select count(*) from approval_svc.approvals_approvalchain "
                "where status = 'rejected' and created_at >= date_trunc('month', now())"
            )
            overdue = scalar("select count(*) from workflow_svc.workflows_workflow where sla_status = 'overdue'")
            avg_days = scalar(
                "select coalesce(avg(extract(epoch from (created_at - lag_created)) / 86400), 0) "
                "from (select created_at, min(created_at) over (partition by workflow_id) as lag_created "
                "from approval_svc.approvals_approvalrecord) records"
            )
            compliant = 100 if total == 0 else round(((total - overdue) / total) * 100, 2)
            return {
                "total_workflows": total,
                "pending_approval": pending,
                "approved_this_month": approved_month,
                "rejected_this_month": rejected_month,
                "sla_compliance_pct": compliant,
                "avg_approval_time_days": round(float(avg_days or 0), 2),
            }

        return response.Response(AnalyticsService.cached_payload("analytics:dashboard", compute))


class SLAReportView(views.APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        def compute():
            return {
                "items": rows(
                    "select coalesce(wt.name, w.approval_type, 'Unknown') as workflow_type, "
                    "coalesce(w.student_faculty, '') as faculty, count(*) as total, "
                    "sum(case when w.sla_status = 'overdue' then 1 else 0 end) as overdue "
                    "from workflow_svc.workflows_workflow w "
                    "left join workflow_svc.workflows_workflowtype wt on wt.id = w.workflow_type_id "
                    "group by 1, 2 order by 1, 2"
                )
            }

        return response.Response(AnalyticsService.cached_payload("analytics:sla-report", compute))


class WorkflowVolumeView(views.APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        period = request.query_params.get("period", "month")
        grain = {"week": "day", "month": "day", "year": "month"}.get(period, "day")
        def compute():
            return {
                "period": period,
                "points": rows(
                    f"select date_trunc('{grain}', created_at) as bucket, count(*) as count "
                    "from workflow_svc.workflows_workflow group by 1 order by 1"
                ),
            }

        return response.Response(AnalyticsService.cached_payload(f"analytics:volume:{period}", compute))


class ApproverPerformanceView(views.APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        def compute():
            return {
                "approvers": rows(
                    "select actor_id as approver_id, actor_name, count(*) as total_decisions, "
                    "avg(extract(epoch from created_at - min_created_at) / 86400) as avg_response_time_days, "
                    "round(100.0 * sum(case when action = 'rejected' then 1 else 0 end) / greatest(count(*), 1), 2) as rejection_rate "
                    "from (select *, min(created_at) over (partition by workflow_id) as min_created_at "
                    "from approval_svc.approvals_approvalrecord where action in ('approved', 'rejected', 'returned')) r "
                    "group by actor_id, actor_name order by total_decisions desc"
                )
            }

        return response.Response(AnalyticsService.cached_payload("analytics:approver-performance", compute))


class RejectionRatesView(views.APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        def compute():
            return {
                "items": rows(
                    "select coalesce(wt.name, w.approval_type, 'Unknown') as workflow_type, "
                    "count(*) as total, "
                    "sum(case when w.status = 'rejected' then 1 else 0 end) as rejected, "
                    "round(100.0 * sum(case when w.status = 'rejected' then 1 else 0 end) / greatest(count(*), 1), 2) as rejection_rate "
                    "from workflow_svc.workflows_workflow w "
                    "left join workflow_svc.workflows_workflowtype wt on wt.id = w.workflow_type_id "
                    "group by 1 order by rejection_rate desc"
                )
            }

        return response.Response(AnalyticsService.cached_payload("analytics:rejection_rates", compute))


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
