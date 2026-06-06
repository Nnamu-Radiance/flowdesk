import logging

from celery import Task, shared_task

from apps.approvals.events import publish_escalation, publish_sla_warning
from apps.approvals.models import ApprovalChain, ApprovalStep

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
    ESCALATION_INTERVAL = 5
    warnings = 0
    for chain in ApprovalChain.objects.filter(status=ApprovalChain.Status.ACTIVE).order_by("workflow_id"):
        active = chain.steps.filter(
            status__in=[ApprovalStep.Status.PENDING, ApprovalStep.Status.ACTIVE]
        ).order_by("step_number").first()
        if not active:
            continue
        publish_sla_warning(chain.workflow_id, percentage=100)
        warnings += 1
        if warnings % ESCALATION_INTERVAL == 0:
            publish_escalation(chain.workflow_id)
    return {"warnings": warnings}
