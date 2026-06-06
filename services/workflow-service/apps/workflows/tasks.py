import logging

from celery import Task, shared_task

logger = logging.getLogger(__name__)

WORKFLOW_TYPE_FIELDS = {
    "approval_type",
    "description",
    "department",
    "priority",
    "tags",
    "required_docs",
    "form_fields",
    "approval_chain",
    "all_documents_required",
    "expected_output",
    "sla_days",
    "is_active",
}


class RetryTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_kwargs = {"max_retries": 3}


@shared_task(bind=True, base=RetryTask, queue="workflow")
def process_document(self, workflow_id: int):
    from apps.workflows.events import publish_document_processed
    from apps.workflows.models import Document

    logger.info("process_document_started workflow_id=%s", workflow_id)
    documents = Document.objects.filter(workflow_id=workflow_id)
    for document in documents:
        document.extracted_text = f"Processed {document.filename}"
        document.embedding = [0.1, 0.2, 0.3]
        document.save(update_fields=["extracted_text", "embedding"])

    publish_document_processed(workflow_id)
    logger.info("process_document_completed workflow_id=%s", workflow_id)
    return {"workflow_id": workflow_id, "status": "processed"}


@shared_task(bind=True, base=RetryTask, queue="workflow")
def process_csv_bulk(self, csv_text: str, submitter_id: int):
    from django.db import transaction

    from apps.workflows.csv_import import parse_workflow_config_csv
    from apps.workflows.models import (
        ApprovalStop,
        Workflow,
        WorkflowDocumentRequirement,
    )

    result = parse_workflow_config_csv(csv_text)
    created_count = 0

    with transaction.atomic():
        for row in result.valid_rows:
            workflow = Workflow.objects.create(
                name=row["name"],
                approval_type=row.get("approval_type", ""),
                description=row.get("description", ""),
                priority=row.get("priority", 2),
                tags=row.get("tags", []),
                metadata=row.get("metadata", {}),
                all_documents_required=row.get("all_documents_required", False),
                created_by_id=submitter_id,
                status="draft",
            )

            # Create approval stops from metadata
            stops = row.get("approval_chain", [])
            for i, stop_name in enumerate(stops, start=1):
                ApprovalStop.objects.create(workflow=workflow, name=stop_name, order=i)

            # Create document requirements from metadata
            reqs = row.get("required_docs", [])
            for req_slug in reqs:
                WorkflowDocumentRequirement.objects.create(workflow=workflow, document_slug=req_slug)

            created_count += 1

    return {
        "status": "complete",
        "created": created_count,
        "updated": 0,
        "errors": result.errors[:20],
    }
