import pytest
from rest_framework import status

from tests.factories import UserFactory, WorkflowFactory


@pytest.mark.django_db
def test_list_workflows(api_client):
    user = UserFactory()
    WorkflowFactory.create_batch(2, created_by=user)
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/workflows/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_dashboard_analytics(api_client):
    user = UserFactory()
    WorkflowFactory(created_by=user)
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/analytics/dashboard/")
    assert response.status_code == status.HTTP_200_OK
    assert "totals" in response.data
