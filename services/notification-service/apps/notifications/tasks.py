import logging

from asgiref.sync import async_to_sync
from celery import Task, shared_task
from channels.layers import get_channel_layer

from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


class RetryTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_kwargs = {"max_retries": 3}


@shared_task(bind=True, base=RetryTask, queue="notification")
def send_email_task(self, recipient_id: int, template: str, context: dict):
    logger.info("email_queued recipient_id=%s template=%s", recipient_id, template)
    return {"recipient_id": recipient_id, "template": template, "context": context}


@shared_task(bind=True, base=RetryTask, queue="notification")
def handle_event(self, event: dict):
    payload = event.get("payload", {})
    event_type = event.get("event_type", "unknown")

    recipient_id = payload.get("approver_id") or payload.get("submitter_id") or payload.get("recipient_id")
    if recipient_id:
        Notification.objects.create(
            recipient_id=recipient_id,
            type=event_type,
            title=event_type.replace(".", " ").title(),
            message=str(payload),
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{recipient_id}",
            {"type": "event_message", "type_key": event_type, "payload": payload},
        )

        send_email_task.delay(recipient_id, template=event_type, context=payload)

    return {"handled": event_type}
