import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.approvals.models import ApprovalChain, ApprovalStep, ApprovalType
from apps.approvals.services import ApprovalService
from apps.auth.permissions import IsAdminOrSelf
from apps.notifications import tasks as notification_tasks
from apps.workflows.models import Document, Workflow
from apps.workflows.tasks import process_csv_bulk, process_workflow_document
from tests.factories import UserFactory, WorkflowFactory


@pytest.mark.django_db
def test_approval_service_full_flow():
    submitter = UserFactory()
    approver1 = UserFactory(role_type="approver")
    approver2 = UserFactory(role_type="approver")
    approval_type = ApprovalType.objects.create(name="Standard", sla_hours=24)
    chain = ApprovalChain.objects.create(workflow_type=approval_type, name="Main chain")
    ApprovalStep.objects.create(chain=chain, order=1, approver=approver1)
    ApprovalStep.objects.create(chain=chain, order=2, approver=approver2)

    workflow = WorkflowFactory(
        created_by=submitter, approval_type=approval_type, status="submitted"
    )
    routed = ApprovalService.auto_route_workflow(workflow)
    workflow.refresh_from_db()
    assert routed is True
    assert workflow.assigned_to_id == approver1.id

    result1 = ApprovalService.approve_workflow(workflow, approver1, "ok")
    workflow.refresh_from_db()
    assert result1["status"] == "in_approval"
    assert workflow.assigned_to_id == approver2.id

    result2 = ApprovalService.approve_workflow(workflow, approver2, "ok")
    workflow.refresh_from_db()
    assert result2["status"] == "approved"
    assert workflow.status == "approved"


@pytest.mark.django_db
def test_approval_service_reject_and_reassign():
    submitter = UserFactory()
    approver = UserFactory(role_type="approver")
    replacement = UserFactory(role_type="approver")
    workflow = WorkflowFactory(
        created_by=submitter, assigned_to=approver, status="in_approval"
    )

    result = ApprovalService.reassign_workflow(
        workflow, approver, replacement, "handover"
    )
    workflow.refresh_from_db()
    assert result["status"] == "reassigned"
    assert workflow.assigned_to_id == replacement.id

    result = ApprovalService.reject_workflow(workflow, replacement, "reject")
    workflow.refresh_from_db()
    assert result["status"] == "rejected"
    assert workflow.status == "rejected"


@pytest.mark.django_db
def test_process_workflow_document_task():
    user = UserFactory()
    approval_type = ApprovalType.objects.create(name="TaskType")
    file_obj = SimpleUploadedFile("doc.pdf", b"dummy", content_type="application/pdf")
    document = Document.objects.create(
        filename="doc.pdf",
        document_type="pdf",
        file=file_obj,
        content_hash="h1",
    )
    workflow = Workflow.objects.create(
        name="Doc workflow",
        created_by=user,
        approval_type=approval_type,
        document=document,
    )
    result = process_workflow_document(workflow.id)
    document.refresh_from_db()
    assert result["status"] == "success"
    assert document.extracted_text


@pytest.mark.django_db
def test_process_csv_bulk_task():
    user = UserFactory()
    ApprovalType.objects.create(name="CSVType")
    csv_data = "name,description\nWF1,Desc1\nWF2,Desc2\n"
    result = process_csv_bulk(csv_data, user.id)
    assert result["status"] == "complete"
    assert result["created"] == 2


@pytest.mark.django_db
def test_notification_tasks_and_permission():
    user = UserFactory()
    res = notification_tasks.send_approval_notification(
        workflow_id=5, approver_id=user.id
    )
    assert res["status"] == "sent"
    assert notification_tasks.send_completion_notification(1)["status"] == "complete"
    assert (
        notification_tasks.send_sla_escalation_email(1, "overdue")["status"] == "queued"
    )

    request = type("Req", (), {"user": user})()
    assert IsAdminOrSelf().has_object_permission(request, None, user)


@pytest.mark.django_db
def test_workflow_submit_method():
    user = UserFactory()
    workflow = WorkflowFactory(
        created_by=user,
        status="draft",
        deadline=timezone.now() + timezone.timedelta(days=1),
    )
    workflow.submit(user)
    workflow.refresh_from_db()
    assert workflow.status == "submitted"
