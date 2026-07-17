from django.core.cache import cache
from django.db import connection
from rest_framework import permissions, response, status, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.approvals.models import ApprovalChain, ApprovalRecord, ApprovalStep
from apps.approvals.serializers import ApprovalChainSerializer, ApprovalRecordSerializer
from apps.approvals.services import ApprovalService

APPROVAL_CHAIN_NOT_FOUND = "Approval chain not found"
INSTITUTIONAL_APPROVER_ROLES = {
    "admin_assistant",
    "administrative_assistant",
    "dean",
    "deputy_vice_chancellor",
    "dvc",
    "faculty",
    "faculty_council",
    "faculty_scientific_council",
    "head_of_department",
    "hod",
    "registrar",
    "supervisor",
}


def normalized_role(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("/", "_")


def user_role_values(request) -> set[str]:
    auth = request.auth if isinstance(request.auth, dict) else {}
    return {
        normalized_role(value)
        for value in {
            getattr(request.user, "role", ""),
            getattr(request.user, "approver_type", ""),
            auth.get("role", ""),
            auth.get("approver_type", ""),
        }
        if value
    }


def is_approver_user(request) -> bool:
    if not request.user or not request.user.is_authenticated:
        return False
    roles = user_role_values(request)
    return bool(roles & ({"admin", "approver"} | INSTITUTIONAL_APPROVER_ROLES))


class IsApprover(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_approver_user(request)


class IsAdminOrApprover(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_approver_user(request)


def active_assigned_chain(workflow_id: int, user_id: int):
    return ApprovalChain.objects.filter(
        workflow_id=workflow_id,
        steps__assignee_id=user_id,
        steps__status=ApprovalStep.Status.ACTIVE,
    ).distinct().first()


class PendingApprovalsView(views.APIView):
    permission_classes = [IsApprover]

    def get(self, request):
        chains = ApprovalChain.objects.filter(
            steps__assignee_id=request.user.id,
            steps__status__in=[ApprovalStep.Status.ACTIVE, ApprovalStep.Status.PENDING],
            status=ApprovalChain.Status.ACTIVE,
        ).distinct()
        return response.Response(ApprovalChainSerializer(chains, many=True).data)


class ApprovalDocumentsView(views.APIView):
    permission_classes = [IsApprover]

    def get(self, request, workflow_id: int):
        chain = active_assigned_chain(workflow_id, request.user.id)
        if not chain:
            return response.Response({"detail": "You are not assigned to this workflow"},
                                     status=status.HTTP_403_FORBIDDEN)
        annotated = ApprovalRecord.objects.filter(workflow_id=workflow_id, annotated_document__isnull=False).exclude(
            annotated_document=""
        )
        return response.Response(
            {
                "workflow_id": workflow_id,
                "documents": chain.documents,
                "annotated_documents": ApprovalRecordSerializer(annotated, many=True).data,
            }
        )


class ApprovalDecisionView(views.APIView):
    permission_classes = [IsApprover]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, workflow_id: int):
        chain = ApprovalChain.objects.filter(workflow_id=workflow_id).first()
        if not chain:
            return response.Response({"detail": APPROVAL_CHAIN_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        action = request.data.get("action")
        if action not in {"approved", "rejected", "returned", "approve", "reject", "return"}:
            return response.Response({"detail": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
        comments = request.data.get("comments") or request.data.get("reason", "")
        if action in {"rejected", "reject", "returned", "return"}:
            has_comments = len((comments or "").strip()) >= 10
            has_annotated = bool(request.FILES.get("annotated_document"))
            if not has_comments and not has_annotated:
                return response.Response(
                    {"detail": ("Feedback is required when rejecting or returning a workflow. "
                                "Please provide comments or an annotated document.")},
                )
        try:
            result = ApprovalService.decision(
                chain,
                approver_id=request.user.id,
                action=action,
                comments=comments,
                annotated_document=request.FILES.get("annotated_document"),
                send_feedback_to_student=str(
                    request.data.get(
                        "send_feedback_to_student",
                        "false")).lower() in {
                    "true",
                    "1",
                    "yes",
                    "on"},
                correlation_id=getattr(request, "correlation_id", None),
            )
        except PermissionError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response({"workflow_id": chain.workflow_id, "status": result})


class LegacyApprovalDecisionView(views.APIView):
    permission_classes = [IsApprover]

    def post(self, request, chain_id: int, action: str):
        chain = ApprovalChain.objects.get(pk=chain_id)
        original_mutable = getattr(request.data, "_mutable", None)
        if original_mutable is not None:
            request.data._mutable = True
        request.data["action"] = "approved" if action == "approve" else "rejected"
        if original_mutable is not None:
            request.data._mutable = original_mutable
        return ApprovalDecisionView().post(request, chain.workflow_id)


class ChainApproveView(views.APIView):
    permission_classes = [IsApprover]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, chain_id: int):
        chain = ApprovalChain.objects.filter(pk=chain_id).first()
        if not chain:
            return response.Response({"detail": APPROVAL_CHAIN_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        comments = request.data.get("comments", "")
        try:
            result = ApprovalService.decision(
                chain,
                approver_id=request.user.id,
                action="approve",
                comments=comments,
                correlation_id=getattr(request, "correlation_id", None),
            )
        except PermissionError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response({"workflow_id": chain.workflow_id, "status": result})


class ReassignView(views.APIView):
    permission_classes = [IsApprover]

    def post(self, request, workflow_id: int):
        chain = (ApprovalChain.objects.filter(workflow_id=workflow_id).first()
                 or ApprovalChain.objects.filter(pk=workflow_id).first())
        if not chain:
            return response.Response({"detail": APPROVAL_CHAIN_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        new_assignee = request.data.get("new_assignee_id") or request.data.get("assignee_id")
        if not new_assignee:
            return response.Response({"detail": "new_assignee_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = ApprovalService.reassign(
                chain,
                approver_id=request.user.id,
                new_assignee_id=int(new_assignee),
                reason=request.data.get("reason", ""),
                correlation_id=getattr(request, "correlation_id", None),
            )
        except PermissionError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return response.Response({"workflow_id": chain.workflow_id, "assignee_id": result["new_assignee_id"], **result})


class LegacyReassignView(views.APIView):
    permission_classes = [IsApprover]

    def post(self, request, chain_id: int):
        chain = ApprovalChain.objects.get(pk=chain_id)
        return ReassignView().post(request, chain.workflow_id)


class HistoryView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workflow_id: int):
        if not is_approver_user(request):
            chain = ApprovalChain.objects.filter(workflow_id=workflow_id).first()
            if not chain or chain.student_id != request.user.id:
                return response.Response(
                    {"detail": "You do not have access to this workflow's history."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        records = ApprovalRecord.objects.filter(workflow_id=workflow_id)
        return response.Response(ApprovalRecordSerializer(records, many=True).data)


class LegacyHistoryView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, chain_id: int):
        chain = ApprovalChain.objects.get(pk=chain_id)
        return HistoryView().get(request, chain.workflow_id)


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
