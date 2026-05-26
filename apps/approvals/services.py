from django.db import transaction
from django.utils import timezone

from apps.approvals.models import ApprovalChain, ApprovalRecord


class ApprovalService:
    @staticmethod
    @transaction.atomic
    def auto_route_workflow(workflow):
        chain = (
            ApprovalChain.objects.filter(workflow_type=workflow.approval_type)
            .prefetch_related("steps")
            .first()
        )
        if not chain or not chain.steps.exists():
            return False

        first_step = chain.steps.first()
        workflow.assigned_to = first_step.approver
        workflow.status = "in_approval"
        if not workflow.deadline:
            workflow.deadline = timezone.now() + timezone.timedelta(
                hours=workflow.approval_type.sla_hours
            )
        workflow.save(update_fields=["assigned_to", "status", "deadline", "updated_at"])
        return True

    @staticmethod
    @transaction.atomic
    def approve_workflow(workflow, approver, comments=""):
        if workflow.assigned_to_id != approver.id and not approver.is_staff:
            raise PermissionError("You are not assigned to this workflow")

        ApprovalRecord.objects.create(
            workflow=workflow, approver=approver, action="approve", comments=comments
        )

        chain = (
            ApprovalChain.objects.filter(workflow_type=workflow.approval_type)
            .prefetch_related("steps")
            .first()
        )
        approved_count = ApprovalRecord.objects.filter(
            workflow=workflow, action="approve"
        ).count()

        if chain and approved_count < chain.steps.count():
            next_step = chain.steps.all()[approved_count]
            workflow.assigned_to = next_step.approver
            workflow.save(update_fields=["assigned_to", "updated_at"])
            return {"status": "in_approval", "next_approver": next_step.approver_id}

        workflow.status = "approved"
        workflow.approved_at = timezone.now()
        workflow.assigned_to = None
        workflow.completed_at = timezone.now()
        workflow.save(
            update_fields=[
                "status",
                "approved_at",
                "assigned_to",
                "completed_at",
                "updated_at",
            ]
        )
        return {"status": "approved"}

    @staticmethod
    @transaction.atomic
    def reject_workflow(workflow, approver, comments=""):
        ApprovalRecord.objects.create(
            workflow=workflow, approver=approver, action="reject", comments=comments
        )
        workflow.status = "rejected"
        workflow.rejected_at = timezone.now()
        workflow.save(update_fields=["status", "rejected_at", "updated_at"])
        return {"status": "rejected"}

    @staticmethod
    @transaction.atomic
    def reassign_workflow(workflow, approver, target_user, comments=""):
        ApprovalRecord.objects.create(
            workflow=workflow,
            approver=approver,
            action="reassign",
            comments=comments,
            metadata={"new_assignee_id": target_user.id},
        )
        workflow.assigned_to = target_user
        workflow.save(update_fields=["assigned_to", "updated_at"])
        return {"status": "reassigned", "assigned_to": target_user.id}
