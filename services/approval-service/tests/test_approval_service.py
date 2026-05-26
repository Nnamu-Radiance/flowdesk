import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from unittest.mock import patch

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
            correlation_id=None
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
    
    with patch("apps.approvals.services.publish_approval_completed") as mock_pub:
        status = ApprovalService.decision(chain, 1, "approve")
        assert status == "pending" # Still waiting for step 2
        step1.refresh_from_db()
        assert step1.status == "approved"
        
        status = ApprovalService.decision(chain, 2, "approve")
        assert status == "approved"
        step2.refresh_from_db()
        assert step2.status == "approved"
        mock_pub.assert_called_once()


@pytest.mark.django_db
def test_approval_record_creation(api_client):
    chain = ApprovalChain.objects.create(workflow_id=103, name="Chain 3")
    ApprovalStep.objects.create(chain=chain, order=1, approver_id=1, status="pending")
    
    with patch("apps.approvals.services.ApprovalService.decision", return_value="approved"):
        api_client.post(f"/api/approvals/{chain.id}/approve/", {"comments": "Good"})
        assert ApprovalRecord.objects.filter(chain=chain, approver_id=1, action="approve").exists()
