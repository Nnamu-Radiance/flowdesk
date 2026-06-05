import uuid
from datetime import datetime, timezone

from celery import current_app
from shared.events.publisher import publish_event


def notify_event(event_type: str, payload: dict, correlation_id: str = None) -> dict:
    """Publish to Redis pub/sub AND dispatch directly to the notification Celery queue."""
    event = publish_event(event_type, payload, "approval-service", correlation_id=correlation_id)
    current_app.send_task(
        "apps.notifications.tasks.handle_event",
        args=[event],
        queue="notification",
    )
    return event


def publish_sla_warning(workflow_id: int, assignee_id: int | None, level: str, deadline=None, student_id: int | None = None):
    return notify_event(
        "sla.warning",
        {
            "workflow_id": workflow_id,
            "assignee_id": assignee_id,
            "student_id": student_id,
            "level": level,
            "deadline": deadline.isoformat() if deadline else None,
        },
    )


def publish_escalation(workflow_id: int, assignee_id: int | None, overdue_by_hours: int):
    return notify_event(
        "approval.escalated",
        {
            "workflow_id": workflow_id,
            "assignee_id": assignee_id,
            "overdue_by_hours": overdue_by_hours,
        },
    )
