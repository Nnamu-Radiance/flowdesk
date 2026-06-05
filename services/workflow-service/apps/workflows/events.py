from shared.events.publisher import publish_event


def publish_workflow_created(workflow, correlation_id: str):
    return publish_event(
        "workflow.created",
        {
            "workflow_id": workflow.id,
            "workflow_type_id": workflow.workflow_type_id,
            "workflow_type_name": workflow.workflow_type.name if workflow.workflow_type else workflow.approval_type,
            "approval_chain": workflow.workflow_type.approval_chain if workflow.workflow_type else [],
            "created_by_id": workflow.created_by_id,
            "student_id": workflow.created_by_id,
            "student_name": workflow.student_name,
            "student_matricule": workflow.student_matricule,
            "student_faculty": workflow.student_faculty,
            "deadline": workflow.deadline.isoformat() if workflow.deadline else None,
            "form_data": workflow.form_data,
            "documents": [
                {
                    "id": document.id,
                    "label": document.document_label,
                    "filename": document.filename,
                    "url": document.file.url if document.file else "",
                }
                for document in workflow.documents.all()
            ],
        },
        "workflow-service",
        correlation_id=correlation_id,
    )


def publish_workflow_config_updated(summary: dict, correlation_id: str | None = None):
    return publish_event(
        "workflow_config.updated",
        summary,
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
