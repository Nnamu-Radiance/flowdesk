import logging

from celery import Task, shared_task

from apps.approvals.events import publish_escalation, publish_sla_warning
from apps.approvals.models import ApprovalChain

logger = logging.getLogger(__name__)


class RetryTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_kwargs = {"max_retries": 3}


@shared_task(bind=True, base=RetryTask, queue="approval")
def consume_workflow_created(self, event: dict):
    from apps.approvals.services import ApprovalService

    logger.info("consume_workflow_created workflow_id=%s", event.get("payload", {}).get("workflow_id"))
    ApprovalService.handle_workflow_created(event)


@shared_task(bind=True, base=RetryTask, queue="approval")
def check_sla_deadlines(self):
    warnings = 0
    for chain in ApprovalChain.objects.all():
        if chain.steps.filter(status="pending").exists():
            publish_sla_warning(chain.workflow_id, 75)
            warnings += 1
            if warnings % 5 == 0:
                publish_escalation(chain.workflow_id)
    return {"warnings": warnings}
