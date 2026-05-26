from django.core.cache import cache
from django.db import connection
from rest_framework import permissions, response, status, views
from rest_framework.decorators import api_view, permission_classes

from apps.approvals.models import ApprovalChain, ApprovalRecord
from apps.approvals.serializers import ApprovalChainSerializer, ApprovalRecordSerializer
from apps.approvals.services import ApprovalService


class PendingApprovalsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        chains = ApprovalChain.objects.filter(steps__approver_id=request.user.id, steps__status="pending").distinct()
        return response.Response(ApprovalChainSerializer(chains, many=True).data)


class ApprovalDecisionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, chain_id: int, action: str):
        chain = ApprovalChain.objects.get(pk=chain_id)
        if action not in {"approve", "reject"}:
            return response.Response({"detail": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

        result = ApprovalService.decision(
            chain,
            approver_id=request.user.id,
            action=action,
            comments=request.data.get("comments") or request.data.get("reason", ""),
            correlation_id=getattr(request, "correlation_id", None),
        )
        return response.Response({"workflow_id": chain.workflow_id, "status": result})


class ReassignView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, chain_id: int):
        chain = ApprovalChain.objects.get(pk=chain_id)
        next_step = chain.steps.filter(status="pending").first()
        if not next_step:
            return response.Response({"detail": "No pending step"}, status=status.HTTP_400_BAD_REQUEST)

        next_step.approver_id = int(request.data.get("assignee_id"))
        next_step.save(update_fields=["approver_id"])
        return response.Response({"workflow_id": chain.workflow_id, "assignee_id": next_step.approver_id})


class HistoryView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, chain_id: int):
        chain = ApprovalChain.objects.get(pk=chain_id)
        records = ApprovalRecord.objects.filter(workflow_id=chain.workflow_id)
        return response.Response(ApprovalRecordSerializer(records, many=True).data)


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
