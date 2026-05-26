import pytest

from apps.workflows.permissions import CanViewWorkflow
from tests.factories import UserFactory, WorkflowFactory


@pytest.mark.django_db
def test_can_view_workflow_for_creator(rf):
    user = UserFactory()
    workflow = WorkflowFactory(created_by=user)
    request = rf.get("/")
    request.user = user
    assert CanViewWorkflow().has_object_permission(request, None, workflow)


@pytest.mark.django_db
def test_cannot_view_other_workflow(rf):
    creator = UserFactory()
    other = UserFactory()
    workflow = WorkflowFactory(created_by=creator)
    request = rf.get("/")
    request.user = other
    assert not CanViewWorkflow().has_object_permission(request, None, workflow)
