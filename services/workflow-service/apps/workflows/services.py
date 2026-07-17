import logging
import uuid

from celery import current_app
from django.db import transaction
from django.utils import timezone

from apps.workflows.models import Document, Workflow
from apps.workflows.events import publish_workflow_created

logger = logging.getLogger(__name__)


def check_document_completeness(workflow_instance: Workflow) -> tuple[bool, list[str]]:
    if not workflow_instance.all_documents_required:
        return True, []

    requirements = workflow_instance.document_requirements.filter(is_required=True)
    verified_requirement_ids = set(
        workflow_instance.document_uploads.filter(
            verified=True,
            requirement__is_required=True,
        ).values_list("requirement_id", flat=True)
    )
    missing_labels = [
        requirement.label
        for requirement in requirements
        if requirement.id not in verified_requirement_ids
    ]
    return not missing_labels, missing_labels


class WorkflowService:
    @staticmethod
    def approval_chain_for(workflow: Workflow) -> list[str]:
        if workflow.workflow_type and workflow.workflow_type.approval_chain:
            return workflow.workflow_type.approval_chain

        metadata = workflow.metadata or {}
        stops = sorted(
            [(key, value) for key, value in metadata.items() if key.startswith("stop_")],
            key=lambda item: int(item[0].replace("stop_", "")),
        )
        return [value for _, value in stops]

    @staticmethod
    def workflow_created_event(workflow: Workflow, correlation_id: str | None = None) -> dict:
        form_data = workflow.form_data or {}
        return {
            "payload": {
                "workflow_id": workflow.id,
                "workflow_type_id": workflow.workflow_type_id,
                "workflow_type_name": workflow.workflow_type.name if workflow.workflow_type else workflow.name,
                "approval_chain": WorkflowService.approval_chain_for(workflow),
                "created_by_id": workflow.created_by_id,
                "student_id": workflow.created_by_id,
                "student_name": workflow.student_name or form_data.get("full_name", ""),
                "student_matricule": workflow.student_matricule or form_data.get("matricule", ""),
                "student_faculty": workflow.student_faculty or form_data.get("faculty", ""),
                "student_department": form_data.get("department", ""),
                "deadline": workflow.deadline.isoformat() if workflow.deadline else None,
                "documents": [
                    {
                        "id": document.id,
                        "label": document.document_label,
                        "filename": document.filename,
                        "url": document.file.url if document.file else "",
                    }
                    for document in workflow.documents.all()
                ],
                "form_data": form_data,
                "appeal_round": workflow.appeal_round,
                "appeal_reason": (workflow.metadata or {}).get("appeal_reason", ""),
                "original_rejection_reason": (workflow.metadata or {}).get("rejection_reason", ""),
            },
            "correlation_id": correlation_id or "",
        }

    @staticmethod
    def dispatch_workflow_created(workflow: Workflow, correlation_id: str | None = None) -> None:
        event = WorkflowService.workflow_created_event(workflow, correlation_id)

        def trigger_chain():
            try:
                current_app.send_task(
                    "apps.approvals.tasks.consume_workflow_created",
                    args=[event],
                    queue="approval",
                )
            except Exception:
                logger.exception("workflow_created approval task dispatch failed workflow_id=%s", workflow.id)

        transaction.on_commit(trigger_chain)

        try:
            publish_workflow_created(workflow, correlation_id or "")
        except Exception:
            logger.exception("Best-effort workflow.created Pub/Sub publish failed for workflow_id=%s", workflow.id)

    @staticmethod
    @transaction.atomic
    def submit_workflow(workflow: Workflow, correlation_id: str | None = None):
        if workflow.status != Workflow.Status.DRAFT:
            raise ValueError(f"Cannot submit workflow with status '{workflow.status}'")

        workflow.status = Workflow.Status.SUBMITTED
        workflow.submitted_at = timezone.now()
        if not workflow.deadline:
            workflow.deadline = timezone.now() + timezone.timedelta(days=3)
        workflow.save(update_fields=["status", "submitted_at", "deadline", "updated_at"])
        WorkflowService.dispatch_workflow_created(workflow, correlation_id)
        return workflow

    @staticmethod
    @transaction.atomic
    def create_workflow(name: str, created_by_id: int, file_obj=None, form_data: dict | None = None) -> Workflow:
        form_data = form_data or {}
        workflow = Workflow.objects.create(
            name=name,
            created_by_id=created_by_id,
            status=Workflow.Status.DRAFT,
            form_data=form_data,
            student_name=form_data.get("full_name", ""),
            student_matricule=form_data.get("matricule", ""),
            student_faculty=form_data.get("faculty", ""),
        )
        if file_obj:
            Document.objects.create(
                doc_id=f"DOC-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}",
                workflow=workflow,
                document_label="document",
                filename=file_obj.name,
                document_type=file_obj.name.split(".")[-1].lower(),
                file=file_obj,
            )
        return workflow
