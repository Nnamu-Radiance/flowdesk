import pytest
from django.utils import timezone

from tests.factories import WorkflowFactory


@pytest.mark.django_db
def test_workflow_is_overdue():
    workflow = WorkflowFactory(
        status="in_approval", deadline=timezone.now() - timezone.timedelta(hours=1)
    )
    assert workflow.is_overdue is True


@pytest.mark.django_db
def test_workflow_remaining_time():
    workflow = WorkflowFactory(
        status="draft", deadline=timezone.now() + timezone.timedelta(hours=2)
    )
    assert workflow.remaining_time is not None
