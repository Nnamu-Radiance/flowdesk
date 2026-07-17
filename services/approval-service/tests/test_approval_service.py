import pytest
from datetime import timedelta
from unittest.mock import ANY, patch

from django.utils import timezone
from rest_framework import exceptions
from rest_framework.test import APIClient, APIRequestFactory

from apps.approvals.models import ApprovalChain, ApprovalStep, ApprovalRecord
from apps.approvals.serializers import ApprovalChainSerializer, ApprovalRecordSerializer


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
@pytest.mark.parametrize("role", ["registrar", "hod", "dean", "admin_assistant", "faculty_council", "dvc", "supervisor"])
def test_pending_approvals_allows_institutional_approver_roles(role):
    from apps.approvals.service_user import ServiceUser

    client = APIClient()
    client.force_authenticate(user=ServiceUser(user_id=7, role=role))
    chain = ApprovalChain.objects.create(workflow_id=701, name="Institutional Chain")
    ApprovalStep.objects.create(chain=chain, order=1, approver_id=7, status=ApprovalStep.Status.ACTIVE)

    response = client.get("/api/approvals/pending/")

    assert response.status_code == 200
    assert response.data[0]["workflow_id"] == 701


@pytest.mark.django_db
def test_pending_approvals_allows_approver_type_claim_when_role_is_generic():
    from apps.approvals.service_user import ServiceUser
    from apps.approvals.views import IsApprover

    client = APIClient()
    user = ServiceUser(user_id=8, role="user", approver_type="registrar")
    client.force_authenticate(user=user)
    chain = ApprovalChain.objects.create(workflow_id=702, name="Registrar Chain")
    ApprovalStep.objects.create(chain=chain, order=1, approver_id=8, status=ApprovalStep.Status.ACTIVE)

    response = client.get("/api/approvals/pending/")

    assert response.status_code == 200
    assert response.data[0]["workflow_id"] == 702
    request = APIRequestFactory().get("/api/approvals/pending/")
    request.user = user
    request.auth = {"role": "user", "approver_type": "registrar"}
    assert IsApprover().has_permission(request, None) is True


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

    with patch("apps.approvals.services.publish_event") as mock_publish:
        response = api_client.post(f"/api/approvals/{chain.id}/reassign/", {"assignee_id": 99})

    assert response.status_code == 200
    step.refresh_from_db()
    assert step.approver_id == 99
    assert response.data["assignee_id"] == 99
    mock_publish.assert_called_once_with(
        "approval.requested",
        {"workflow_id": chain.workflow_id, "approver_id": 99},
        correlation_id=ANY,
    )


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
def test_approval_service_return_marks_chain_and_publishes_event():
    from apps.approvals.services import ApprovalService

    chain = ApprovalChain.objects.create(
        workflow_id=305,
        workflow_type_name="Transcript",
        student_id=77,
        total_steps=2,
    )
    current = ApprovalStep.objects.create(
        chain=chain,
        order=1,
        approver_id=1,
        role_required="registrar",
        role_display_name="Registrar",
        status=ApprovalStep.Status.ACTIVE,
    )
    pending = ApprovalStep.objects.create(
        chain=chain,
        order=2,
        approver_id=2,
        role_required="dean",
        role_display_name="Dean",
        status=ApprovalStep.Status.PENDING,
    )

    with patch("apps.approvals.services.publish_event") as mock_publish:
        result = ApprovalService.decision(
            chain,
            approver_id=1,
            action="return",
            comments="Please update the supporting document.",
            send_feedback_to_student=True,
            correlation_id="corr-return",
        )

    chain.refresh_from_db()
    current.refresh_from_db()
    pending.refresh_from_db()
    assert result == "returned"
    assert chain.status == ApprovalChain.Status.RETURNED
    assert current.status == ApprovalStep.Status.RETURNED
    assert pending.status == ApprovalStep.Status.VOID
    mock_publish.assert_called_once()
    event_name, payload = mock_publish.call_args.args
    assert event_name == "approval.returned"
    assert payload["workflow_id"] == chain.workflow_id
    assert payload["student_id"] == 77
    assert payload["workflow_type_name"] == "Transcript"
    assert payload["step_number"] == 1
    assert payload["send_feedback_to_student"] is True
    assert mock_publish.call_args.kwargs["correlation_id"] == "corr-return"


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
def test_history_endpoint_allows_registrar_role():
    from apps.approvals.service_user import ServiceUser

    client = APIClient()
    client.force_authenticate(user=ServiceUser(user_id=321, role="registrar"))
    ApprovalChain.objects.create(workflow_id=710, student_id=999)
    ApprovalRecord.objects.create(workflow_id=710, step_number=1, actor_id=321, action=ApprovalRecord.Action.APPROVED)

    response = client.get("/api/approvals/710/history/")

    assert response.status_code == 200
    assert response.data[0]["workflow_id"] == 710


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


@pytest.mark.django_db
def test_chain_serializer_reports_sla_and_remaining_time():
    now = timezone.now()
    chain = ApprovalChain.objects.create(
        workflow_id=301,
        workflow_type_name="Transcript",
        deadline=now + timedelta(days=2, hours=3),
        total_steps=1,
    )
    ApprovalChain.objects.filter(pk=chain.pk).update(created_at=now - timedelta(days=1))
    chain.refresh_from_db()
    ApprovalStep.objects.create(
        chain=chain,
        order=1,
        approver_id=10,
        role_required="registrar",
        role_display_name="Registrar",
        status=ApprovalStep.Status.ACTIVE,
    )

    data = ApprovalChainSerializer(chain).data

    assert data["workflow_type"] == "Transcript"
    assert data["name"] == "Transcript Approval Chain"
    assert data["sla_percentage"] > 0
    assert data["remaining_time"].endswith("left")
    assert data["steps"][0]["order"] == 1
    assert data["steps"][0]["approver_id"] == 10


@pytest.mark.django_db
def test_chain_serializer_reports_overdue_deadline():
    now = timezone.now()
    chain = ApprovalChain.objects.create(workflow_id=302, deadline=now - timedelta(hours=1))
    ApprovalChain.objects.filter(pk=chain.pk).update(created_at=now - timedelta(days=1))
    chain.refresh_from_db()

    data = ApprovalChainSerializer(chain).data

    assert data["sla_percentage"] == 100
    assert data["remaining_time"] == "Overdue"


@pytest.mark.django_db
def test_record_serializer_exposes_legacy_approver_and_empty_document_url():
    record = ApprovalRecord.objects.create(
        workflow_id=303,
        step_number=1,
        actor_id=22,
        action=ApprovalRecord.Action.COMMENTED,
        comments="Looks fine",
    )

    data = ApprovalRecordSerializer(record).data

    assert data["actor_id"] == 22
    assert data["approver_id"] == 22
    assert data["annotated_document_url"] == ""


def test_jwt_authentication_accepts_bearer_token():
    from apps.approvals.authentication import JWTLocalAuthentication

    request = APIRequestFactory().get("/api/approvals/pending/", HTTP_AUTHORIZATION="Bearer good-token")
    with patch(
        "apps.approvals.authentication.validate_jwt",
        return_value={"user_id": 44, "role": "approver", "approver_type": "registrar"},
    ):
        user, payload = JWTLocalAuthentication().authenticate(request)

    assert user.id == 44
    assert user.role == "approver"
    assert user.approver_type == "registrar"
    assert payload["user_id"] == 44


def test_jwt_authentication_ignores_missing_bearer_token():
    from apps.approvals.authentication import JWTLocalAuthentication

    request = APIRequestFactory().get("/api/approvals/pending/")

    assert JWTLocalAuthentication().authenticate(request) is None


def test_jwt_authentication_rejects_invalid_token():
    from apps.approvals.authentication import JWTLocalAuthentication

    request = APIRequestFactory().get("/api/approvals/pending/", HTTP_AUTHORIZATION="Bearer bad-token")
    with patch("apps.approvals.authentication.validate_jwt", side_effect=ValueError("bad")):
        with pytest.raises(exceptions.AuthenticationFailed):
            JWTLocalAuthentication().authenticate(request)


def test_resolve_approver_scopes_dean_by_faculty():
    from apps.approvals.services import resolve_approver

    with patch("requests.get") as mock_get:
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = [{"id": 42}]

        approver_id = resolve_approver("Dean", faculty="ICT", department="Computer Science")

    assert approver_id == 42
    params = mock_get.call_args.kwargs["params"]
    assert params["role"] == "approver"
    assert params["approver_type"] == "dean"
    assert params["faculty"] == "ICT"
