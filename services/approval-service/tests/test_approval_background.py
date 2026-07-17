import pytest
from unittest.mock import patch

from apps.approvals.events import publish_escalation, publish_sla_warning
from apps.approvals.models import ApprovalChain, ApprovalStep
from apps.approvals.services import ApprovalService
from apps.approvals.tasks import check_sla_deadlines, consume_workflow_created


def test_publish_sla_warning_delegates_to_shared_publisher():
    with patch("apps.approvals.events.publish_event") as mock_publish:
        publish_sla_warning(workflow_id=55, percentage=75)

    mock_publish.assert_called_once_with(
        "sla.warning",
        {"workflow_id": 55, "percentage": 75},
        "approval-service",
    )


def test_publish_escalation_delegates_to_shared_publisher():
    with patch("apps.approvals.events.publish_event") as mock_publish:
        publish_escalation(workflow_id=99)

    mock_publish.assert_called_once_with(
        "approval.escalated",
        {"workflow_id": 99},
        "approval-service",
    )


@pytest.mark.django_db
def test_consume_workflow_created_task_calls_service_handler():
    event = {"payload": {"workflow_id": 9001}, "correlation_id": "corr-9001"}
    with patch("apps.approvals.services.ApprovalService.handle_workflow_created") as mock_handle:
        consume_workflow_created.run(event)

    mock_handle.assert_called_once_with(event)


@pytest.mark.django_db
def test_check_sla_deadlines_emits_warnings_and_periodic_escalation():
    for idx in range(1, 7):
        chain = ApprovalChain.objects.create(workflow_id=idx, name=f"Chain {idx}")
        ApprovalStep.objects.create(chain=chain, order=1, approver_id=idx, status="pending")

    with patch("apps.approvals.tasks.publish_sla_warning") as mock_warning, patch(
        "apps.approvals.tasks.publish_escalation"
    ) as mock_escalation:
        result = check_sla_deadlines.run()

    assert result == {"warnings": 6}
    assert mock_warning.call_count == 6
    mock_escalation.assert_called_once_with(5)


@pytest.mark.django_db
def test_handle_workflow_created_creates_default_chain_and_first_event():
    event = {"payload": {"workflow_id": 321}, "correlation_id": "corr-321"}

    with patch("apps.approvals.services.publish_event") as mock_publish:
        chain = ApprovalService.handle_workflow_created(event)

    steps = list(chain.steps.order_by("order").values_list("order", "approver_id", "role_required"))
    assert chain.workflow_id == 321
    assert chain.name == "Default Chain"
    assert steps == [(1, 2, "approver"), (2, 3, "approver")]
    mock_publish.assert_called_once_with(
        "approval.requested",
        {"workflow_id": 321, "approver_id": 2},
        correlation_id="corr-321",
    )


@pytest.mark.django_db
def test_decision_reject_marks_step_and_publishes_decision_only():
    chain = ApprovalChain.objects.create(workflow_id=333, name="Reject Chain")
    step = ApprovalStep.objects.create(chain=chain, order=1, approver_id=11, status="pending")

    with patch("apps.approvals.services.publish_event") as mock_publish:
        status = ApprovalService.decision(
            chain,
            approver_id=11,
            action="reject",
            comments="Not acceptable",
            correlation_id="corr-reject",
        )

    step.refresh_from_db()
    assert status == "rejected"
    assert step.status == "rejected"
    mock_publish.assert_called_once()
    event_name, payload = mock_publish.call_args.args
    assert event_name == "approval.decision"
    assert payload["workflow_id"] == chain.workflow_id
    assert payload["decision"] == "rejected"
    assert payload["approver_id"] == 11
    assert payload["decided_at"]
    assert mock_publish.call_args.kwargs["correlation_id"] == "corr-reject"
