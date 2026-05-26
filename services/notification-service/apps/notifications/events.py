from apps.notifications.tasks import handle_event


def handle_approval_requested(event: dict):
    return handle_event.delay(event)


def handle_approval_decision(event: dict):
    return handle_event.delay(event)


def handle_sla_warning(event: dict):
    return handle_event.delay(event)


def handle_approval_escalated(event: dict):
    return handle_event.delay(event)
