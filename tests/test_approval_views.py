import pytest
from rest_framework import status

from tests.factories import UserFactory, WorkflowFactory


@pytest.mark.django_db
def test_pending_approvals_endpoint(api_client):
    approver = UserFactory(role_type="approver")
    WorkflowFactory(status="in_approval", assigned_to=approver, created_by=approver)
    api_client.force_authenticate(user=approver)
    response = api_client.get("/api/approvals/pending/")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data, list)


@pytest.mark.django_db
def test_approve_reject_reassign_endpoints(api_client):
    approver = UserFactory(role_type="approver")
    replacement = UserFactory(role_type="approver")
    workflow = WorkflowFactory(
        status="in_approval", assigned_to=approver, created_by=approver
    )

    api_client.force_authenticate(user=approver)
    approve_response = api_client.patch(
        "/api/approvals/approve/",
        {"workflow_id": workflow.id, "comments": "ok"},
        format="json",
    )
    assert approve_response.status_code == status.HTTP_200_OK

    workflow.refresh_from_db()
    workflow.status = "in_approval"
    workflow.assigned_to = approver
    workflow.save(update_fields=["status", "assigned_to", "updated_at"])

    reassign_response = api_client.patch(
        "/api/approvals/reassign/",
        {
            "workflow_id": workflow.id,
            "assigned_to": replacement.id,
            "comments": "handover",
        },
        format="json",
    )
    assert reassign_response.status_code == status.HTTP_200_OK

    api_client.force_authenticate(user=replacement)
    reject_response = api_client.patch(
        "/api/approvals/reject/",
        {"workflow_id": workflow.id, "comments": "reject"},
        format="json",
    )
    assert reject_response.status_code == status.HTTP_200_OK
