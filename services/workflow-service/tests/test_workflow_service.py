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
    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_workflow_crud(api_client):
    # List
    response = api_client.get("/api/workflows/")
    assert response.status_code == 200

    # Create
    response = api_client.post("/api/workflows/", {"name": "Test Workflow"}, format="json")
    assert response.status_code == 201
    assert Workflow.objects.filter(name="Test Workflow", created_by_id=1).exists()

    # Detail
    wf = Workflow.objects.get(name="Test Workflow")
    response = api_client.get(f"/api/workflows/{wf.id}/")
    assert response.status_code == 200


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


@pytest.mark.django_db
def test_csv_process(api_client):
    from io import BytesIO
    csv_content = b"name,description\nWF1,Desc1\nWF2,Desc2"
    csv_file = BytesIO(csv_content)
    csv_file.name = "test.csv"

    with patch("apps.workflows.tasks.process_csv_bulk.delay") as mock_task:
        mock_task.return_value = MagicMock(id="task-123")
        response = api_client.post("/api/workflows/csv-process/", {"file": csv_file}, format="multipart")
        assert response.status_code == 202
        assert response.data["task_id"] == "task-123"


@pytest.mark.django_db
def test_process_document_task():
    from apps.workflows.tasks import process_document
    from apps.workflows.models import Document
    
    workflow = Workflow.objects.create(name="DocWF", created_by_id=1)
    Document.objects.create(workflow=workflow, filename="test.pdf", doc_id="DOC1")
    
    with patch("apps.workflows.events.publish_document_processed") as mock_pub:
        result = process_document(workflow.id)
        assert result["status"] == "processed"
        doc = Document.objects.get(workflow=workflow)
        assert "Processed" in doc.extracted_text
        mock_pub.assert_called_once_with(workflow.id)


@pytest.mark.django_db
def test_process_csv_bulk_task():
    from apps.workflows.tasks import process_csv_bulk
    csv_text = "name,description\nWF1,D1\nWF2,D2"
    result = process_csv_bulk(csv_text, 1)
    assert result["created"] == 2
    assert Workflow.objects.filter(created_by_id=1).count() == 2
