from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import permissions, response
from rest_framework.views import APIView

from apps.workflows.models import Workflow


class DashboardAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        base = Workflow.objects.all()
        data = {
            "generated_at": timezone.now(),
            "totals": {
                "workflows": base.count(),
                "approved": base.filter(status="approved").count(),
                "in_approval": base.filter(status="in_approval").count(),
                "overdue": base.filter(sla_status="overdue").count(),
            },
            "status_breakdown": list(
                base.values("status").annotate(count=Count("id")).order_by("status")
            ),
            "avg_priority": base.aggregate(avg_priority=Avg("priority"))[
                "avg_priority"
            ],
        }
        return response.Response(data)
