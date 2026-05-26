import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from unittest.mock import patch, MagicMock

from apps.workflows.models import Workflow


@pytest.fixture
def api_client():
    from apps.workflows.service_user import ServiceUser
    client = APIClient()
    user = ServiceUser(user_id=1, role="submitter")
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/health/")
    assert response.status_code in {200, 503}


@pytest.mark.django_db
def test_list_requires_authentication():
    client = APIClient()
    response = client.get("/api/workflows/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_workflow_crud(api_client):
    # List
    response = api_client.get("/api/workflows/")
    assert response.status_code == 200

    # Create
    response = api_client.post("/api/workflows/", {"name": "Test Workflow"}, format="json")
    assert response.status_code == 201
    assert Workflow.objects.filter(name="Test Workflow", created_by_id=1).exists()


@pytest.mark.django_db
def test_workflow_submit(api_client):
    workflow = Workflow.objects.create(name="Submittable", created_by_id=1)
    
    with patch("apps.workflows.views.publish_workflow_created") as mock_publish:
        response = api_client.patch(f"/api/workflows/{workflow.id}/submit/")
        assert response.status_code == 200
        workflow.refresh_from_db()
        assert workflow.status == "submitted"
        mock_publish.assert_called_once()


@pytest.mark.django_db
def test_csv_dry_run(api_client):
    from io import BytesIO
    csv_content = b"name,description\nWF1,Desc1\nWF2,Desc2"
    csv_file = BytesIO(csv_content)
    csv_file.name = "test.csv"

    response = api_client.post("/api/workflows/csv-dry-run/", {"file": csv_file}, format="multipart")
    assert response.status_code == 200
    assert response.data["valid_rows"] == 2
    assert "job_id" in response.data
