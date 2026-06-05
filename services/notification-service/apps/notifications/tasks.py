import logging

from asgiref.sync import async_to_sync
from celery import Task, shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


class RetryTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_kwargs = {"max_retries": 3}


EVENT_CONFIG = {
    "workflow.created": {
        "recipient": ("student_id", "created_by_id", "submitter_id"),
        "template": "workflow_received",
        "title": "Workflow Received",
        "message": "Your request has been received and is now in the approval process.",
    },
    "approval.requested": {
        "recipient": ("assignee_id", "approver_id", "student_id"),
        "template": "approval_requested",
        "title": "Approval Requested",
        "message": "A workflow is awaiting your decision.",
    },
    "approval.decision": {
        "recipient": ("student_id",),
        "template": None,
        "title": "Workflow Decision",
        "message": "A final decision has been recorded for your workflow.",
    },
    "approval.returned": {
        "recipient": ("student_id",),
        "template": "workflow_returned",
        "title": "Changes Requested",
        "message": "Changes were requested for your workflow.",
    },
    "approval.step_completed": {
        "recipient": ("student_id", "created_by_id"),
        "template": None,
        "title": "Approval Step Completed",
        "message": "Your workflow has moved to the next approval step.",
    },
    "approval.approved": {
        "recipient": ("student_id", "created_by_id"),
        "template": None,
        "title": "Workflow Approved",
        "message": "Your workflow has been fully approved.",
    },
    "approval.rejected": {
        "recipient": ("student_id", "created_by_id"),
        "template": None,
        "title": "Workflow Rejected",
        "message": "Your workflow has been rejected.",
    },
    "sla.warning": {
        "recipient": ("assignee_id", "approver_id", "student_id"),
        "template": "sla_warning",
        "title": "SLA Warning",
        "message": "A workflow deadline is approaching.",
    },
    "approval.escalated": {
        "recipient": ("assignee_id", "approver_id"),
        "template": "escalation_alert",
        "title": "Approval Escalated",
        "message": "A workflow approval is overdue.",
    },
}


def recipients_for(event_type: str, payload: dict) -> list[int]:
    config = EVENT_CONFIG.get(event_type, {})
    recipients = []
    for key in config.get("recipient", ("recipient_id",)):
        value = payload.get(key)
        if value:
            recipients.append(int(value))
    if event_type == "approval.escalated" and payload.get("admin_id"):
        recipients.append(int(payload["admin_id"]))
    return list(dict.fromkeys(recipients))


def template_for(event_type: str, payload: dict) -> str:
    if event_type == "approval.decision":
        return "workflow_approved" if payload.get("status") == "approved" else "workflow_rejected"
    return EVENT_CONFIG.get(event_type, {}).get("template") or event_type.replace(".", "_")


def message_for(event_type: str, payload: dict, fallback: str) -> str:
    workflow = payload.get("workflow_type_name") or payload.get("workflow_name") or "workflow"
    if event_type == "approval.step_completed":
        role = payload.get("role_display_name") or payload.get("completed_role") or "an approver"
        next_role = payload.get("next_role_display_name") or payload.get("next_role") or "the next approver"
        return f"Your {workflow} has been approved by {role}. Next step: {next_role}."
    if event_type == "approval.approved":
        return f"Your {workflow} has been fully approved."
    if event_type == "approval.rejected":
        comments = payload.get("comments") or payload.get("final_comments") or ""
        return f"Your {workflow} has been rejected. Reason: {comments}"
    if event_type == "approval.returned":
        comments = payload.get("comments") or payload.get("final_comments") or ""
        return f"Your {workflow} has been returned for corrections. Feedback: {comments}"
    return payload.get("message") or fallback


@shared_task(bind=True, base=RetryTask, queue="notification")
def send_email_task(self, recipient_id: int, template: str, context: dict):
    recipient_email = context.get("recipient_email") or context.get("email")
    html_body = render_to_string(f"notifications/{template}.html", context)
    text_body = render_to_string(f"notifications/{template}.txt", context)
    if recipient_email:
        send_mail(
            subject=context.get("subject", "FlowDesk notification"),
            message=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", ""),
            recipient_list=[recipient_email],
            html_message=html_body,
            fail_silently=False,
        )
    logger.info("email_rendered recipient_id=%s template=%s sent=%s", recipient_id, template, bool(recipient_email))
    return {"recipient_id": recipient_id, "template": template, "sent": bool(recipient_email)}


@shared_task(bind=True, base=RetryTask, queue="notification")
def handle_event(self, event: dict):
    payload = event.get("payload", {})
    event_type = event.get("event_type", "unknown")
    config = EVENT_CONFIG.get(event_type, {})
    recipients = recipients_for(event_type, payload)
    channel_layer = get_channel_layer() if recipients else None

    for recipient_id in recipients:
        message = message_for(event_type, payload, config.get("message", str(payload)))
        notification = Notification.objects.create(
            recipient_id=recipient_id,
            type=event_type,
            title=config.get("title", event_type.replace(".", " ").title()),
            message=message,
            workflow_id=payload.get("workflow_id"),
        )

        async_to_sync(channel_layer.group_send)(
            f"user_{recipient_id}",
            {
                "type": "notification.message",
                "type_key": event_type,
                "payload": {
                    **payload,
                    "message": message,
                    "notification_id": notification.id,
                    "timestamp": timezone.now().isoformat(),
                },
            },
        )

        if config.get("template") is not None or event_type == "approval.decision":
            send_email_task.delay(recipient_id, template=template_for(event_type, payload), context=payload)

    return {"handled": event_type, "recipients": recipients}
