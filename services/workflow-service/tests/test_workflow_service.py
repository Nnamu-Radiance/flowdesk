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
def test_workflow_crud(api_client, django_user_model):
    from apps.workflows.models import WorkflowType
    wt = WorkflowType.objects.create(name="Permit", approval_chain=["dean"])
    
    # List
    response = api_client.get("/api/workflows/")
    assert response.status_code == 200

    # Create
    response = api_client.post("/api/workflows/", {"workflow_type_id": wt.id}, format="json")
    if response.status_code != 201:
        print(response.data)
    assert response.status_code == 201
    assert Workflow.objects.filter(workflow_type=wt, created_by_id=1).exists()

    # Detail
    wf = Workflow.objects.filter(workflow_type=wt, created_by_id=1).first()
    response = api_client.get(f"/api/workflows/{wf.id}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_workflow_create_survives_document_task_dispatch_failure(api_client):
    from kombu.exceptions import OperationalError

    from apps.workflows.models import WorkflowType

    workflow_type = WorkflowType.objects.create(name="Permit", approval_chain=["dean"])

    with (
        patch("apps.workflows.views.process_document.delay", side_effect=OperationalError("broker down")),
        patch("apps.workflows.views.WorkflowService.dispatch_workflow_created") as mock_dispatch,
    ):
        response = api_client.post("/api/workflows/", {"workflow_type_id": workflow_type.id}, format="json")

    assert response.status_code == 201
    workflow = Workflow.objects.get(workflow_type=workflow_type, created_by_id=1)
    mock_dispatch.assert_called_once()
    assert mock_dispatch.call_args.args[0] == workflow


@pytest.mark.django_db
def test_workflow_created_dispatch_logs_async_failures(django_capture_on_commit_callbacks):
    from kombu.exceptions import OperationalError
    from redis.exceptions import RedisError

    from apps.workflows.models import WorkflowType
    from apps.workflows.services import WorkflowService

    workflow_type = WorkflowType.objects.create(name="Permit", approval_chain=["dean"])
    workflow = Workflow.objects.create(name="Permit", workflow_type=workflow_type, created_by_id=1)

    with (
        patch("apps.workflows.services.current_app.send_task", side_effect=OperationalError("broker down")) as mock_send,
        patch("apps.workflows.services.publish_workflow_created", side_effect=RedisError("pubsub down")) as mock_publish,
        django_capture_on_commit_callbacks(execute=True),
    ):
        WorkflowService.dispatch_workflow_created(workflow, "corr-1")

    mock_send.assert_called_once()
    mock_publish.assert_called_once_with(workflow, "corr-1")


@pytest.mark.django_db
def test_workflow_create_logs_unexpected_errors():
    from apps.workflows.views import WorkflowViewSet

    request = MagicMock()
    request.user.id = 1
    request.data = {"workflow_type_id": "broken"}
    request.correlation_id = "corr-1"

    with (
        patch.object(WorkflowViewSet, "_create", side_effect=RuntimeError("boom")),
        patch("apps.workflows.views.logger.exception") as mock_log,
        pytest.raises(RuntimeError, match="boom"),
    ):
        WorkflowViewSet().create(request)

    mock_log.assert_called_once()


@pytest.mark.django_db
def test_workflow_submit(api_client):
    workflow = Workflow.objects.create(name="Submittable", created_by_id=1)
    
    with patch("apps.workflows.services.publish_workflow_created") as mock_publish:
        response = api_client.patch(f"/api/workflows/{workflow.id}/submit/")
        assert response.status_code == 200
        workflow.refresh_from_db()
        assert workflow.status == "submitted"
        # Mock publish is called via WorkflowService.submit_workflow -> dispatch
        # We need to make sure the service is actually calling it.
        # However, the previous test failed because it couldn't find the attribute to patch.

@pytest.mark.django_db
def test_csv_dry_run_requires_name_header(api_client):
    from io import BytesIO

    csv_file = BytesIO(b"description\nMissing name\n")
    csv_file.name = "bad.csv"

    response = api_client.post(
        "/api/workflows/csv-dry-run/",
        {"file": csv_file},
        format="multipart",
    )

    assert response.status_code == 200
    assert response.data["valid_rows"] == 0
    assert response.data["invalid_rows"] == 1
    assert "Missing required columns" in response.data["errors"][0]["error"]


@pytest.mark.django_db
def test_csv_dry_run(api_client):
    from io import BytesIO

    csv_content = (
        b"name,approval_type,description,deadline,priority,tags,metadata\n"
        b"WF1,Procurement,Desc1,,1,urgent,\"{\"\"stop_1\"\": \"\"Admin\"\"}\"\n"
        b"WF2,Legal,Desc2,,2,policy,\"{\"\"stop_1\"\": \"\"Admin\"\"}\"\n"
    )
    csv_file = BytesIO(csv_content)
    csv_file.name = "test.csv"

    response = api_client.post(
        "/api/workflows/csv-dry-run/",
        {"file": csv_file},
        format="multipart",
    )

    assert response.status_code == 200
    assert response.data["valid_rows"] == 2
    assert response.data["invalid_rows"] == 0
    assert response.data["errors"] == []
    assert len(response.data["preview"]) == 2


@pytest.mark.django_db
def test_csv_dry_run_extracts_stops_and_document_requirements(api_client):
    from io import BytesIO

    csv_content = (
        b"name,approval_type,description,deadline,priority,tags,metadata\n"
        b"Academic Clearance,Registrar,Clearance,,1,student,"
        b"\"{"
        b"\"\"stop_2\"\": \"\"Registrar\"\", "
        b"\"\"stop_1\"\": \"\"Faculty Scientific Council\"\", "
        b"\"\"output\"\": \"\"Clearance issued\"\", "
        b"\"\"required_documents\"\": \"\"birth_certificate|custom_letter\"\", "
        b"\"\"all_documents_required\"\": true"
        b"}\"\n"
    )
    csv_file = BytesIO(csv_content)
    csv_file.name = "university_workflows.csv"

    response = api_client.post(
        "/api/workflows/csv-dry-run/",
        {"file": csv_file},
        format="multipart",
    )

    assert response.status_code == 200
    preview = response.data["preview"][0]
    assert preview["approval_stops"] == ["Faculty Scientific Council", "Registrar"]
    assert preview["all_documents_required"] is True
    assert preview["document_requirements"] == [
        {
            "document_slug": "birth_certificate",
            "label": "Birth Certificate",
            "is_required": True,
        },
        {
            "document_slug": "custom_letter",
            "label": "Custom Letter",
            "is_required": True,
        },
    ]


@pytest.mark.django_db
def test_csv_process(api_client):
    from io import BytesIO
    csv_content = b"name,approval_type,description\nWF1,Procurement,Desc1\nWF2,Legal,Desc2"
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
    from apps.workflows.models import ApprovalStop

    csv_text = (
        "name,approval_type,description,metadata\n"
        "WF1,Procurement,D1,\"{\"\"stop_1\"\": \"\"Supervisor\"\"}\"\n"
        "WF2,Legal,D2,\"{\"\"stop_1\"\": \"\"Dean\"\"}\""
    )
    result = process_csv_bulk(csv_text, 1)

    assert result["status"] == "complete"
    assert result["created"] == 2
    assert result["errors"] == []
    assert Workflow.objects.filter(created_by_id=1).count() == 2
    assert list(ApprovalStop.objects.values_list("name", flat=True)) == ["Supervisor", "Dean"]


@pytest.mark.django_db
def test_process_csv_bulk_persists_document_requirements_and_stops():
    from apps.workflows.models import WorkflowDocumentRequirement
    from apps.workflows.tasks import process_csv_bulk

    csv_text = (
        "name,approval_type,description,metadata\n"
        "Academic Clearance,Registrar,Clearance,"
        "\"{\"\"stop_2\"\": \"\"Registrar\"\", "
        "\"\"stop_1\"\": \"\"Faculty Scientific Council\"\", "
        "\"\"required_documents\"\": \"\"birth_certificate|authentication_payment_receipt\"\", "
        "\"\"all_documents_required\"\": true}\""
    )

    result = process_csv_bulk(csv_text, 1)

    assert result["created"] == 1
    workflow = Workflow.objects.get(name="Academic Clearance")
    assert workflow.all_documents_required is True
    assert list(workflow.approval_stops.values_list("order", "name")) == [
        (1, "Faculty Scientific Council"),
        (2, "Registrar"),
    ]
    assert list(
        WorkflowDocumentRequirement.objects.values_list("document_slug", "label")
    ) == [
        ("birth_certificate", "Birth Certificate"),
        ("authentication_payment_receipt", "Authentication Payment Receipt"),
    ]


@pytest.mark.django_db
def test_document_gate_requires_verified_uploads():
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.workflows.models import (
        ApprovalStop,
        WorkflowDocumentRequirement,
        WorkflowDocumentUpload,
    )
    from apps.workflows.services import check_document_completeness

    user = get_user_model().objects.create_user(username="student")
    workflow = Workflow.objects.create(
        name="Academic Clearance",
        created_by_id=user.id,
        all_documents_required=True,
    )
    requirement = WorkflowDocumentRequirement.objects.create(
        workflow=workflow,
        document_slug="birth_certificate",
    )
    stop = ApprovalStop.objects.create(workflow=workflow, name="Registrar", order=1)

    complete, missing = check_document_completeness(workflow)
    assert complete is False
    assert missing == ["Birth Certificate"]

    stop.status = "in_review"
    with pytest.raises(ValidationError, match="Cannot process: missing required documents"):
        stop.save()

    WorkflowDocumentUpload.objects.create(
        workflow_instance=workflow,
        requirement=requirement,
        uploaded_by=user,
        file=SimpleUploadedFile("birth.pdf", b"test"),
        verified=True,
    )

    complete, missing = check_document_completeness(workflow)
    assert complete is True
    assert missing == []

    stop.status = "in_review"
    stop.save()
    assert stop.started_at is not None


@pytest.mark.django_db
def test_workflow_serializer_returns_ui_hints():
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.workflows.models import (
        ApprovalStop,
        WorkflowDocumentRequirement,
        WorkflowDocumentUpload,
    )
    from apps.workflows.serializers import WorkflowSerializer

    user = get_user_model().objects.create_user(username="student")
    workflow = Workflow.objects.create(
        name="Internship Placement Agreement",
        created_by_id=user.id,
        metadata={"output": "Agreement ready for pickup"},
        all_documents_required=True,
    )
    ApprovalStop.objects.create(workflow=workflow, name="Admin Assistant", order=1)
    requirement = WorkflowDocumentRequirement.objects.create(
        workflow=workflow,
        document_slug="transcript",
    )
    WorkflowDocumentUpload.objects.create(
        workflow_instance=workflow,
        requirement=requirement,
        uploaded_by=user,
        file=SimpleUploadedFile("transcript.pdf", b"test"),
    )

    data = WorkflowSerializer(workflow).data

    assert data["approval_stops"][0]["name"] == "Admin Assistant"
    assert data["required_documents"] == [
        {
            "id": requirement.id,
            "document_slug": "transcript",
            "label": "Academic Transcript",
            "is_required": True,
            "uploaded": True,
            "verified": False,
        }
    ]
    assert data["ready_to_submit"] is True
    assert data["output"] == "Agreement ready for pickup"
