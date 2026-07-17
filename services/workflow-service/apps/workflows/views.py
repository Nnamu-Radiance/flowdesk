import json
import logging
import uuid
from datetime import timedelta

from celery.exceptions import CeleryError
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone
from kombu.exceptions import KombuError
from rest_framework import permissions, response, status, views, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.workflows.csv_import import parse_workflow_config_csv
from apps.workflows.events import publish_workflow_config_updated
from apps.workflows.models import Document, Workflow, WorkflowConfigUpload, WorkflowType
from apps.workflows.serializers import WorkflowSerializer, WorkflowTypeSerializer
from apps.workflows.services import WorkflowService
from apps.workflows.tasks import process_csv_bulk, process_document

WORKFLOW_TYPE_FIELDS = {
    "name",
    "approval_type",
    "description",
    "department",
    "priority",
    "tags",
    "required_docs",
    "form_fields",
    "approval_chain",
    "all_documents_required",
    "expected_output",
    "sla_days",
    "is_active",
}

logger = logging.getLogger(__name__)


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, "role", "") == "admin")


class IsSubmitter(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, "role", "") == "submitter")


class IsAuthenticatedOrInternalService(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.headers.get("X-Internal-Service"):
            return True
        return bool(request.user and request.user.is_authenticated)


def profile_claim(request, key, default=""):
    payload = request.auth if isinstance(request.auth, dict) else {}
    return payload.get(key) or getattr(request.user, key, default) or default


def serialize_csv_preview_row(row):
    return {
        **row,
        "deadline": row.get("deadline") or None,
    }


class WorkflowConfigListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = WorkflowType.objects.filter(is_active=True).order_by("name")
        return response.Response(WorkflowTypeSerializer(queryset, many=True).data)


class WorkflowConfigDetailView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        workflow_type = WorkflowType.objects.get(pk=pk, is_active=True)
        return response.Response(WorkflowTypeSerializer(workflow_type).data)


class WorkflowConfigUploadView(views.APIView):
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return response.Response({"detail": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST)

        text = csv_file.read().decode("utf-8")
        csv_file.seek(0)
        result = parse_workflow_config_csv(text)
        created = 0
        updated = 0
        if not result.errors:
            seen_names = []
            for row in result.valid_rows:
                seen_names.append(row["name"])
                _, was_created = WorkflowType.objects.update_or_create(
                    name=row["name"],
                    defaults={key: value for key, value in row.items(
                    ) if key in WORKFLOW_TYPE_FIELDS and key != "name"},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            WorkflowType.objects.exclude(name__in=seen_names).update(is_active=False)

        upload = WorkflowConfigUpload.objects.create(
            uploaded_by_id=request.user.id,
            file=csv_file,
            created=created,
            updated=updated,
            errors=result.errors,
        )
        summary = {
            "created": created,
            "updated": updated,
            "errors": result.errors,
            "uploaded_at": upload.uploaded_at.isoformat(),
        }
        if not result.errors:
            publish_workflow_config_updated(summary, getattr(request, "correlation_id", None))
        return response.Response(summary, status=status.HTTP_200_OK)


class WorkflowViewSet(viewsets.ModelViewSet):
    serializer_class = WorkflowSerializer
    permission_classes = [IsAuthenticatedOrInternalService]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action == "create":
            return [IsSubmitter()]
        return super().get_permissions()

    def get_queryset(self):
        qs = Workflow.objects.select_related("workflow_type").prefetch_related("documents").order_by("-created_at")
        if not self.request.headers.get("X-Internal-Service") and getattr(self.request.user, "role", "") != "admin":
            qs = qs.filter(created_by_id=self.request.user.id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=False, methods=["post"], url_path="csv-dry-run")
    def csv_dry_run(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return response.Response({"detail": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST)

        result = parse_workflow_config_csv(csv_file.read().decode("utf-8"))
        return response.Response(
            {
                "valid_rows": len(result.valid_rows),
                "invalid_rows": result.invalid_rows,
                "errors": result.errors[:20],
                "preview": [serialize_csv_preview_row(row) for row in result.valid_rows[:10]],
            }
        )

    @action(detail=False, methods=["post"], url_path="csv-process")
    def csv_process(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return response.Response({"detail": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST)

        task = process_csv_bulk.delay(csv_file.read().decode("utf-8"), request.user.id)
        return response.Response({"task_id": task.id, "status": "processing"}, status=status.HTTP_202_ACCEPTED)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            return self._create(request, *args, **kwargs)
        except Exception:
            logger.exception(
                "workflow create failed user_id=%s workflow_type_id=%s correlation_id=%s",
                getattr(request.user, "id", None),
                request.data.get("workflow_type_id") or request.data.get("workflow_type"),
                getattr(request, "correlation_id", None),
            )
            raise

    def _create(self, request, *args, **kwargs):
        workflow_type_id = request.data.get("workflow_type_id") or request.data.get("workflow_type")
        if not workflow_type_id:
            return response.Response({"detail": "workflow_type_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        workflow_type = WorkflowType.objects.filter(pk=workflow_type_id, is_active=True).first()
        if not workflow_type:
            return response.Response({"detail": "Workflow type not found"}, status=status.HTTP_400_BAD_REQUEST)

        raw_form_data = request.data.get("form_data", {})
        if isinstance(raw_form_data, str):
            try:
                form_data = json.loads(raw_form_data or "{}")
            except json.JSONDecodeError:
                return response.Response({"detail": "form_data must be valid JSON"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            form_data = dict(raw_form_data)

        required_fields = set(workflow_type.form_fields)
        missing_fields = [field for field in required_fields if field not in form_data or form_data.get(field) is None]
        for field in ["faculty", "department", "matricule", "full_name"]:
            claim_value = profile_claim(request, field)
            if claim_value and field in required_fields and not form_data.get(field):
                form_data[field] = claim_value
                if field in missing_fields:
                    missing_fields.remove(field)
        if missing_fields:
            return response.Response({"detail": "Missing form fields", "fields": missing_fields},
                                     status=status.HTTP_400_BAD_REQUEST)

        document_labels = request.data.get("document_labels", "[]")
        if isinstance(document_labels, str):
            try:
                document_labels = json.loads(document_labels)
            except json.JSONDecodeError:
                document_labels = []
        files = request.FILES.getlist("documents")
        label_to_file = {label: files[index] for index, label in enumerate(document_labels) if index < len(files)}
        for label in workflow_type.required_docs:
            keyed_file = request.FILES.get(f"document_{label}") or request.FILES.get(label)
            if keyed_file:
                label_to_file[label] = keyed_file
        uploaded_required_docs = [label for label in workflow_type.required_docs if label in label_to_file]
        if workflow_type.required_docs and workflow_type.all_documents_required:
            missing_docs = [label for label in workflow_type.required_docs if label not in label_to_file]
            if missing_docs:
                return response.Response({"detail": "Missing required documents",
                                         "documents": missing_docs}, status=status.HTTP_400_BAD_REQUEST)
        elif workflow_type.required_docs and not uploaded_required_docs:
            return response.Response(
                {"detail": "At least one required document must be uploaded", "documents": workflow_type.required_docs},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submitted_at = timezone.now()
        student_name = profile_claim(request, "full_name") or profile_claim(request, "name") or request.user.username
        workflow = Workflow.objects.create(
            workflow_type=workflow_type,
            name=f"{workflow_type.name} - {student_name} - {submitted_at.date().isoformat()}",
            description=workflow_type.description,
            approval_type=workflow_type.approval_type,
            status=Workflow.Status.SUBMITTED,
            created_by_id=request.user.id,
            student_name=student_name,
            student_matricule=profile_claim(request, "matricule"),
            student_faculty=profile_claim(request, "faculty") or form_data.get("faculty", ""),
            form_data=form_data,
            deadline=submitted_at + timedelta(days=workflow_type.sla_days),
            submitted_at=submitted_at,
            priority=workflow_type.priority,
            tags=workflow_type.tags,
            metadata={"expected_output": workflow_type.expected_output},
            all_documents_required=workflow_type.all_documents_required,
        )

        for label, file_obj in label_to_file.items():
            Document.objects.create(
                doc_id=f"DOC-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}",
                workflow=workflow,
                document_label=label,
                filename=file_obj.name,
                document_type=file_obj.name.split(".")[-1].lower(),
                file=file_obj,
            )

        try:
            process_document.delay(workflow.id)
        except (CeleryError, KombuError, OSError):
            logger.exception("workflow document task dispatch failed workflow_id=%s", workflow.id)
        WorkflowService.dispatch_workflow_created(
            workflow,
            getattr(request, "correlation_id", None) or str(uuid.uuid4()),
        )
        return response.Response(WorkflowSerializer(
            workflow, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        workflow = self.get_object()
        payload = workflow.metadata or {}
        current_step = payload.get(
            "current_step",
            1 if workflow.status in {"submitted", "in_approval"} else 0,
        )
        total_steps = payload.get(
            "total_steps",
            len(workflow.workflow_type.approval_chain) if workflow.workflow_type else 0,
        )
        return response.Response({
            "current_step": current_step,
            "total_steps": total_steps,
            "current_office": payload.get("current_office", "Awaiting assignment"),
            "steps_completed": payload.get("steps_completed", 0),
            "steps_remaining": payload.get("steps_remaining", 0),
            "status": workflow.status,
            "latest_comment": payload.get("latest_comment", ""),
        })

    @action(detail=True, methods=["patch"])
    def submit(self, request, pk=None):
        workflow = self.get_object()
        correlation_id = getattr(request, "correlation_id", None) or str(uuid.uuid4())
        try:
            workflow = WorkflowService.submit_workflow(workflow, correlation_id=correlation_id)
        except ValueError as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(WorkflowSerializer(workflow).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def appeal(self, request, pk=None):
        workflow = self.get_object()
        if workflow.created_by_id != request.user.id:
            return response.Response({"detail": "Only the submitter can appeal this workflow."},
                                     status=status.HTTP_403_FORBIDDEN)
        if workflow.status not in {Workflow.Status.REJECTED, Workflow.Status.RETURNED}:
            return response.Response(
                {"detail": "Appeals are only allowed for rejected or returned workflows."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        appeal_reason = (request.data.get("appeal_reason") or "").strip()
        if len(appeal_reason) < 10:
            return response.Response(
                {"detail": "appeal_reason must be at least 10 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        metadata = dict(workflow.metadata or {})
        metadata["appeal_reason"] = appeal_reason
        workflow.appeal_round += 1
        workflow.status = Workflow.Status.SUBMITTED
        workflow.metadata = metadata
        workflow.save(update_fields=["appeal_round", "status", "metadata", "updated_at"])
        correlation_id = getattr(request, "correlation_id", None) or str(uuid.uuid4())
        WorkflowService.dispatch_workflow_created(workflow, correlation_id)
        return response.Response(WorkflowSerializer(workflow, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    checks = {"database": "error", "cache": "error"}
    details = {}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception as exc:
        details["database"] = str(exc)

    try:
        cache.set("health", "ok", 10)
        checks["cache"] = "ok"
    except Exception as exc:
        details["cache"] = str(exc)

    healthy = all(value == "ok" for value in checks.values())
    payload = {"status": "healthy" if healthy else "unhealthy", **checks}
    if details:
        payload["details"] = details
    return response.Response(
        payload,
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
