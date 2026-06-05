import csv
from io import StringIO

from celery import Task, shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


class RetryTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_kwargs = {"max_retries": 3}


@shared_task(bind=True, base=RetryTask)
def process_workflow_document(self, workflow_id: int):
    from apps.workflows.models import Workflow

    workflow = Workflow.objects.select_related("document").get(id=workflow_id)
    doc = workflow.document
    if not doc:
        logger.info("Workflow %s has no document", workflow_id)
        return {"status": "skipped"}

    doc.extracted_text = f"Indexed document {doc.filename}"
    doc.indexed_at = timezone.now()
    doc.embedding = [0.1, 0.2, 0.3]
    doc.save(update_fields=["extracted_text", "indexed_at", "embedding"])
    logger.info("Processed workflow document %s", workflow_id)
    return {"status": "success", "workflow_id": workflow_id}


@shared_task(bind=True, base=RetryTask, time_limit=300)
def process_csv_bulk(self, file_content: str, user_id: int):
    from apps.auth.models import CustomUser
    from apps.workflows.csv_import import parse_workflow_csv
    from apps.workflows.models import Workflow

    user = CustomUser.objects.get(id=user_id)
    result = parse_workflow_csv(file_content)
    created = 0

    for row in result.valid_rows:
        Workflow.objects.create(created_by=user, **row)
        created += 1

    return {
        "status": "complete",
        "created": created,
        "errors": result.errors[:20],
    }


@shared_task(bind=True, base=RetryTask)
def escalate_sla_deadlines(self):
    from apps.notifications.tasks import send_sla_escalation_email
    from apps.workflows.models import Workflow

    now = timezone.now()
    workflows = Workflow.objects.filter(status="in_approval", deadline__isnull=False)
    escalated = 0
    for workflow in workflows:
        if workflow.deadline <= now:
            workflow.sla_status = "overdue"
            workflow.save(update_fields=["sla_status", "updated_at"])
            send_sla_escalation_email.delay(workflow.id, "overdue")
            escalated += 1
    return {"escalated": escalated}