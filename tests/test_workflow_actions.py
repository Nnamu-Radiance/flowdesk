import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from apps.approvals.models import ApprovalType
from apps.workflows.models import Document
from tests.factories import UserFactory, WorkflowFactory


@pytest.mark.django_db
def test_workflow_submit_action(api_client):
    user = UserFactory()
    workflow = WorkflowFactory(created_by=user, status="draft")
    api_client.force_authenticate(user=user)
    response = api_client.post(f"/api/workflows/{workflow.id}/submit/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_csv_actions(api_client):
    user = UserFactory()
    ApprovalType.objects.create(name="BulkType")
    api_client.force_authenticate(user=user)

    csv_bytes = io.BytesIO(b"name,description\nA,one\nB,two\n")
    dry_run_file = SimpleUploadedFile(
        "dry.csv", csv_bytes.getvalue(), content_type="text/csv"
    )
    dry_response = api_client.post(
        "/api/workflows/csv_dry_run/", {"file": dry_run_file}, format="multipart"
    )
    assert dry_response.status_code == status.HTTP_200_OK
    assert dry_response.data["valid_rows"] == 2

    process_file = SimpleUploadedFile(
        "bulk.csv", csv_bytes.getvalue(), content_type="text/csv"
    )
    process_response = api_client.post(
        "/api/workflows/csv_process/", {"file": process_file}, format="multipart"
    )
    assert process_response.status_code == status.HTTP_202_ACCEPTED


@pytest.mark.django_db
def test_workflow_create_endpoint(api_client):
    user = UserFactory()
    approval_type = ApprovalType.objects.create(name="CreateType")
    doc_file = SimpleUploadedFile("demo.pdf", b"test", content_type="application/pdf")
    document = Document.objects.create(
        filename="demo.pdf",
        document_type="pdf",
        file=doc_file,
        content_hash="doc-create-hash",
    )

    api_client.force_authenticate(user=user)
    payload = {
        "name": "Created workflow",
        "description": "desc",
        "approval_type": approval_type.id,
        "document": document.id,
    }
    response = api_client.post("/api/workflows/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
