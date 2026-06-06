import pytest
from rest_framework.test import APIClient
from unittest.mock import ANY, patch

from apps.approvals.models import ApprovalChain, ApprovalStep, ApprovalRecord


@pytest.fixture
def api_client():
    from apps.approvals.service_user import ServiceUser
    client = APIClient()
    user = ServiceUser(user_id=1, role="approver")
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/health/")
    assert response.status_code in {200, 503}


@pytest.mark.django_db
def test_pending_approvals(api_client):
    chain = ApprovalChain.objects.create(workflow_id=101, name="Chain 1")
    ApprovalStep.objects.create(chain=chain, order=1, approver_id=1, status="pending")
    
    response = api_client.get("/api/approvals/pending/")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["workflow_id"] == 101


@pytest.mark.django_db
def test_approval_decision(api_client):
    chain = ApprovalChain.objects.create(workflow_id=101, name="Chain 1")
    ApprovalStep.objects.create(chain=chain, order=1, approver_id=1, status="pending")
    
    with patch("apps.approvals.services.ApprovalService.decision") as mock_decision:
        mock_decision.return_value = "approved"
        response = api_client.post(f"/api/approvals/{chain.id}/approve/", {"comments": "Looks good"})
        assert response.status_code == 200
        assert response.data["status"] == "approved"
        mock_decision.assert_called_once_with(
            chain,
            approver_id=1,
            action="approve",
            comments="Looks good",
            correlation_id=ANY,
        )


@pytest.mark.django_db
def test_reassign(api_client):
    chain = ApprovalChain.objects.create(workflow_id=101, name="Chain 1")
    step = ApprovalStep.objects.create(chain=chain, order=1, approver_id=1, status="pending")
    
    response = api_client.post(f"/api/approvals/{chain.id}/reassign/", {"assignee_id": 99})
    assert response.status_code == 200
    step.refresh_from_db()
    assert step.approver_id == 99
    assert response.data["assignee_id"] == 99


@pytest.mark.django_db
def test_approval_service_logic():
    from apps.approvals.services import ApprovalService
    from apps.approvals.models import ApprovalChain, ApprovalStep
    
    chain = ApprovalChain.objects.create(workflow_id=102, name="Chain 2")
    step1 = ApprovalStep.objects.create(chain=chain, order=1, approver_id=1, status="pending")
    step2 = ApprovalStep.objects.create(chain=chain, order=2, approver_id=2, status="pending")
    
    with patch("apps.approvals.services.publish_event") as mock_pub:
        status = ApprovalService.decision(chain, 1, "approve", "step 1")
        assert status == "in_approval"  # Still waiting for step 2
        step1.refresh_from_db()
        assert step1.status == "approved"
        
        status = ApprovalService.decision(chain, 2, "approve", "step 2")
        assert status == "approved"
        step2.refresh_from_db()
        assert step2.status == "approved"
        assert mock_pub.call_count == 3


@pytest.mark.django_db
def test_approval_record_creation(api_client):
    chain = ApprovalChain.objects.create(workflow_id=103, name="Chain 3")
    ApprovalStep.objects.create(chain=chain, order=1, approver_id=1, status="pending")

    with patch("apps.approvals.services.publish_event"):
        response = api_client.post(f"/api/approvals/{chain.id}/approve/", {"comments": "Good"})
    assert response.status_code == 200
    assert ApprovalRecord.objects.filter(workflow_id=chain.workflow_id, approver_id=1, action="approve").exists()


@pytest.mark.django_db
def test_history_endpoint(api_client):
    ApprovalChain.objects.create(workflow_id=110, name="Chain")
    response = api_client.get("/api/approvals/110/history/")
    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_history_endpoint_non_privileged():
    from apps.approvals.service_user import ServiceUser
    client = APIClient()
    student = ServiceUser(user_id=999, role="student")
    client.force_authenticate(user=student)

    chain = ApprovalChain.objects.create(workflow_id=111, student_id=999)
    response = client.get("/api/approvals/111/history/")
    assert response.status_code == 200

    other_chain = ApprovalChain.objects.create(workflow_id=112, student_id=888)
    response = client.get("/api/approvals/112/history/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_legacy_history_endpoint(api_client):
    chain = ApprovalChain.objects.create(workflow_id=113, name="Chain")
    response = api_client.get(f"/api/approvals/chains/{chain.id}/history/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_decision_view_not_found(api_client):
    response = api_client.post("/api/approvals/9999/decide/", {"action": "approve", "comments": "ok"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_decision_view_invalid_action(api_client):
    ApprovalChain.objects.create(workflow_id=200)
    response = api_client.post("/api/approvals/200/decide/", {"action": "invalid"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_approval_decision_by_workflow_id(api_client):
    chain = ApprovalChain.objects.create(workflow_id=201, name="Chain")
    ApprovalStep.objects.create(chain=chain, order=1, approver_id=1, status="pending")

    with patch("apps.approvals.services.ApprovalService.decision") as mock_decision:
        mock_decision.return_value = "approved"
        response = api_client.post("/api/approvals/201/decide/", {"action": "approve", "comments": "OK"})
    assert response.status_code == 200
    assert response.data["status"] == "approved"


@pytest.mark.django_db
def test_legacy_approve_route(api_client):
    chain = ApprovalChain.objects.create(workflow_id=202, name="Chain")
    ApprovalStep.objects.create(chain=chain, order=1, approver_id=1, status="pending")

    with patch("apps.approvals.services.ApprovalService.decision") as mock_decision:
        mock_decision.return_value = "approved"
        response = api_client.post(f"/api/approvals/chains/{chain.id}/approve/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_reassign_not_found(api_client):
    response = api_client.post("/api/approvals/9999/reassign/", {"assignee_id": 5})
    assert response.status_code == 404


@pytest.mark.django_db
def test_chain_approve_not_found(api_client):
    response = api_client.post("/api/approvals/9999/approve/", {"comments": "ok"})
    assert response.status_code == 404
