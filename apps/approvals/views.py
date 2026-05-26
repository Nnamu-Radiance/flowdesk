from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.approvals.models import ApprovalRecord
from apps.approvals.permissions import CanApprove
from apps.approvals.serializers import ApprovalRecordSerializer
from apps.approvals.services import ApprovalService
from apps.workflows.models import Workflow


class ApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApprovalRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return ApprovalRecord.objects.select_related("workflow", "approver")
        return ApprovalRecord.objects.select_related("workflow", "approver").filter(
            workflow__assigned_to=user
        )

    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def pending(self, request):
        workflows = Workflow.objects.filter(
            status="in_approval", assigned_to=request.user
        ).select_related("document")
        payload = [
            {
                "workflow_id": w.id,
                "name": w.name,
                "document": w.document.filename if w.document else None,
                "deadline": w.deadline,
            }
            for w in workflows
        ]
        return Response(payload)

    @action(
        detail=False,
        methods=["patch"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def approve(self, request):
        workflow = Workflow.objects.get(pk=request.data.get("workflow_id"))
        if not CanApprove().has_object_permission(request, self, workflow):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        result = ApprovalService.approve_workflow(
            workflow, request.user, request.data.get("comments", "")
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["patch"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def reject(self, request):
        workflow = Workflow.objects.get(pk=request.data.get("workflow_id"))
        if not CanApprove().has_object_permission(request, self, workflow):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        result = ApprovalService.reject_workflow(
            workflow, request.user, request.data.get("comments", "")
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["patch"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def reassign(self, request):
        workflow = Workflow.objects.get(pk=request.data.get("workflow_id"))
        target_user = workflow.created_by.__class__.objects.get(
            pk=request.data.get("assigned_to")
        )
        result = ApprovalService.reassign_workflow(
            workflow,
            request.user,
            target_user,
            request.data.get("comments", ""),
        )
        return Response(result, status=status.HTTP_200_OK)
