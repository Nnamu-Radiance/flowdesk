from django.conf import settings
from django.core.management.base import BaseCommand

from apps.approvals.models import ApprovalChain
from apps.approvals.services import ApprovalService


class Command(BaseCommand):
    help = "Rebuild approval chains for all submitted workflows"

    def handle(self, *args, **options):
        import requests

        ApprovalChain.objects.all().delete()
        self.stdout.write("Cleared all existing chains.")

        response = requests.get(
            f"{settings.WORKFLOW_SERVICE_URL}/api/workflows/?status=submitted",
            headers={"X-Internal-Service": "approval-service"},
            timeout=10,
        )
        if not response.ok:
            self.stdout.write(f"Could not fetch workflows: {response.status_code}")
            return

        data = response.json()
        workflows = data.get("results", data) if isinstance(data, dict) else data

        for workflow in workflows:
            self.stdout.write(f"Rebuilding chain for workflow {workflow['id']} - {workflow['name']}")
            metadata = workflow.get("metadata") or {}
            stops = sorted(
                [(key, value) for key, value in metadata.items() if key.startswith("stop_")],
                key=lambda item: int(item[0].replace("stop_", "")),
            )
            approval_chain = [value for _, value in stops]
            if not approval_chain:
                workflow_type = workflow.get("workflow_type_detail") or {}
                approval_chain = workflow_type.get("approval_chain") or []

            form_data = workflow.get("form_data") or {}
            event = {
                "payload": {
                    "workflow_id": workflow["id"],
                    "workflow_type_name": workflow["name"],
                    "approval_chain": approval_chain,
                    "created_by_id": workflow["created_by_id"],
                    "student_id": workflow["created_by_id"],
                    "student_name": workflow.get("student_name", ""),
                    "student_matricule": workflow.get("student_matricule", ""),
                    "student_faculty": workflow.get("student_faculty", ""),
                    "student_department": form_data.get("department", ""),
                    "deadline": workflow.get("deadline"),
                    "documents": workflow.get("documents") or [],
                    "form_data": form_data,
                },
                "correlation_id": "",
            }

            try:
                chain = ApprovalService.handle_workflow_created(event)
                self.stdout.write(f"  Created chain {chain.id} with {chain.total_steps} steps")
                for step in chain.steps.order_by("step_number"):
                    self.stdout.write(
                        f"    step {step.step_number}: {step.role_display_name} -> assignee_id={step.assignee_id}"
                    )
            except Exception as exc:
                self.stdout.write(f"  FAILED: {exc}")
