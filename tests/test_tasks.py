import pytest

from apps.workflows.tasks import escalate_sla_deadlines
from tests.factories import WorkflowFactory


@pytest.mark.django_db
def test_escalate_sla_deadlines_marks_overdue():
    workflow = WorkflowFactory(status="in_approval")
    workflow.deadline = workflow.created_at
    workflow.save(update_fields=["deadline"])
    result = escalate_sla_deadlines()
    assert "escalated" in result
