import logging

from celery import Task, shared_task
from django.utils import timezone

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
    warnings = 0
    for chain in ApprovalChain.objects.filter(status=ApprovalChain.Status.ACTIVE, deadline__isnull=False):
        active = chain.steps.filter(status=ApprovalStep.Status.ACTIVE).first()
        if not active:
            continue
        total = (chain.deadline - chain.created_at).total_seconds()
        elapsed = (timezone.now() - chain.created_at).total_seconds()
        pct = int((elapsed / total) * 100) if total > 0 else 100
        if pct >= 100:
            overdue_by_hours = max(int((timezone.now() - chain.deadline).total_seconds() // 3600), 0)
            publish_escalation(chain.workflow_id, active.assignee_id, overdue_by_hours)
            warnings += 1
        elif pct >= 75:
            publish_sla_warning(chain.workflow_id, active.assignee_id, "75%", chain.deadline, student_id=chain.student_id)
            warnings += 1
        elif pct >= 50:
            publish_sla_warning(chain.workflow_id, active.assignee_id, "50%", chain.deadline, student_id=chain.student_id)
            warnings += 1
    return {"warnings": warnings}
