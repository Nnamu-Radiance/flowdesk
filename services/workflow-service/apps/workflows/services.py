from django.utils import timezone

from apps.workflows.models import Workflow


class WorkflowService:
    @staticmethod
    def submit_workflow(workflow: Workflow):
        workflow.status = "submitted"
        if not workflow.deadline:
            workflow.deadline = timezone.now() + timezone.timedelta(days=3)
        workflow.save(update_fields=["status", "deadline", "updated_at"])
        return workflow
