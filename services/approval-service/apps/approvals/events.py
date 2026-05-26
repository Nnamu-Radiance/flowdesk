from shared.events.publisher import publish_event


def publish_sla_warning(workflow_id: int, percentage: int):
    return publish_event(
        "sla.warning",
        {"workflow_id": workflow_id, "percentage": percentage},
        "approval-service",
    )


def publish_escalation(workflow_id: int):
    return publish_event(
        "approval.escalated",
        {"workflow_id": workflow_id},
        "approval-service",
    )
