from shared.events.publisher import publish_event


def publish_workflow_created(workflow_id: int, submitter_id: int, deadline: str | None, correlation_id: str):
    return publish_event(
        "workflow.created",
        {"workflow_id": workflow_id, "submitter_id": submitter_id, "deadline": deadline},
        "workflow-service",
        correlation_id=correlation_id,
    )


def publish_document_processed(workflow_id: int, correlation_id: str | None = None):
    return publish_event(
        "workflow.document_processed",
        {"workflow_id": workflow_id},
        "workflow-service",
        correlation_id=correlation_id,
    )
