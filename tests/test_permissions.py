import pytest

from apps.workflows.permissions import CanViewWorkflow
from apps.auth.permissions import IsAdminUser
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


def test_admin_permission_accepts_admin_token(rf):
    request = rf.get("/")
    request.user = type("TokenUser", (), {"is_authenticated": True})()
    request.auth = {"role": "admin"}

    assert IsAdminUser().has_permission(request, None)


def test_admin_permission_rejects_non_admin_token(rf):
    request = rf.get("/")
    request.user = type("TokenUser", (), {"is_authenticated": True})()
    request.auth = {"role": "submitter"}

    assert not IsAdminUser().has_permission(request, None)
