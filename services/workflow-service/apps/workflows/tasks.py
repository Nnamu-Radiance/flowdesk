import logging

from celery import Task, shared_task

logger = logging.getLogger(__name__)


class RetryTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_kwargs = {"max_retries": 3}


@shared_task(bind=True, base=RetryTask, queue="workflow")
def process_document(self, workflow_id: int):
    from apps.workflows.events import publish_document_processed
    from apps.workflows.models import Document

    logger.info("process_document_started workflow_id=%s", workflow_id)
    document = Document.objects.select_related("workflow").get(workflow_id=workflow_id)
    document.extracted_text = f"Processed {document.filename}"
    document.embedding = [0.1, 0.2, 0.3]
    document.save(update_fields=["extracted_text", "embedding"])

    publish_document_processed(workflow_id)
    logger.info("process_document_completed workflow_id=%s", workflow_id)
    return {"workflow_id": workflow_id, "status": "processed"}


@shared_task(bind=True, base=RetryTask, queue="workflow")
def process_csv_bulk(self, csv_text: str, submitter_id: int):
    from apps.workflows.models import Workflow

    created = 0
    lines = [line for line in csv_text.splitlines() if line.strip()]
    for line in lines[1:]:
        parts = line.split(",")
        name = parts[0].strip()
        if name:
            Workflow.objects.create(name=name, created_by_id=submitter_id)
            created += 1

    return {"created": created}
