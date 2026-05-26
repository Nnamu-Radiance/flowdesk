from django.db import transaction
from django.utils import timezone

from apps.approvals.models import ApprovalChain, ApprovalRecord, ApprovalStep
from shared.events.publisher import publish_event


class ApprovalService:
    @staticmethod
    @transaction.atomic
    def handle_workflow_created(event: dict):
        payload = event.get("payload", {})
        workflow_id = payload["workflow_id"]
        chain = ApprovalChain.objects.create(workflow_id=workflow_id, workflow_type="standard", name="Default Chain")
        ApprovalStep.objects.create(chain=chain, order=1, approver_id=2, role_required="approver")
        ApprovalStep.objects.create(chain=chain, order=2, approver_id=3, role_required="approver")
        publish_event(
            "approval.requested",
            {"workflow_id": workflow_id, "approver_id": 2},
            "approval-service",
            correlation_id=event.get("correlation_id"),
        )
        return chain

    @staticmethod
    @transaction.atomic
    def decision(chain: ApprovalChain, approver_id: int, action: str, comments: str, correlation_id: str | None = None):
        ApprovalRecord.objects.create(
            workflow_id=chain.workflow_id,
            approver_id=approver_id,
            action=action,
            comments=comments,
        )

        current = chain.steps.filter(approver_id=approver_id, status="pending").first()
        if current:
            current.status = "approved" if action == "approve" else "rejected"
            current.save(update_fields=["status"])

        if action == "reject":
            status_value = "rejected"
        elif chain.steps.filter(status="pending").exists():
            status_value = "in_approval"
            next_step = chain.steps.filter(status="pending").first()
            publish_event(
                "approval.requested",
                {"workflow_id": chain.workflow_id, "approver_id": next_step.approver_id},
                "approval-service",
                correlation_id=correlation_id,
            )
        else:
            status_value = "approved"

        publish_event(
            "approval.decision",
            {
                "workflow_id": chain.workflow_id,
                "decision": status_value,
                "approver_id": approver_id,
                "decided_at": timezone.now().isoformat(),
            },
            "approval-service",
            correlation_id=correlation_id,
        )
        return status_value
