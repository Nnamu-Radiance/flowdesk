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
    from apps.workflows.csv_import import parse_workflow_config_csv
    from apps.workflows.models import WorkflowType

    result = parse_workflow_config_csv(csv_text)
    created = 0
    updated = 0

    for row in result.valid_rows:
        _, was_created = WorkflowType.objects.update_or_create(
            name=row["name"],
            defaults={key: value for key, value in row.items() if key in WORKFLOW_TYPE_FIELDS},
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {
        "status": "complete",
        "created": created,
        "updated": updated,
        "errors": result.errors[:20],
    }
