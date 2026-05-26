from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer

logger = get_task_logger(__name__)


@shared_task
def send_approval_notification(workflow_id: int, approver_id: int):
    from apps.notifications.models import Notification

    message = f"Workflow #{workflow_id} requires your approval"
    Notification.objects.create(
        user_id=approver_id, notification_type="approval", message=message
    )

    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{approver_id}",
                {
                    "type": "approval_notification",
                    "payload": {
                        "type": "approval",
                        "message": message,
                        "workflow_id": workflow_id,
                    },
                },
            )
    except Exception:
        logger.warning(
            "WebSocket broadcast skipped for workflow_id=%s approver_id=%s",
            workflow_id,
            approver_id,
        )

    return {"status": "sent"}


@shared_task
def send_completion_notification(workflow_id: int):
    return {"workflow_id": workflow_id, "status": "complete"}


@shared_task
def send_sla_escalation_email(workflow_id: int, level: str):
    return {"workflow_id": workflow_id, "level": level, "status": "queued"}
