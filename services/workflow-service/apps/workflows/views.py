import uuid

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework import permissions, response, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser

from apps.workflows.events import publish_workflow_created
from apps.workflows.models import CSVImportJob, Document, Workflow
from apps.workflows.serializers import WorkflowSerializer
from apps.workflows.services import WorkflowService
from apps.workflows.tasks import process_csv_bulk, process_document


class WorkflowViewSet(viewsets.ModelViewSet):
    serializer_class = WorkflowSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Workflow.objects.filter(created_by_id=self.request.user.id).order_by("-created_at")

    def perform_create(self, serializer):
        workflow = serializer.save(created_by_id=self.request.user.id)
        file_obj = self.request.FILES.get("document")
        if file_obj:
            doc_id = f"DOC-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"
            Document.objects.create(
                doc_id=doc_id,
                workflow=workflow,
                filename=file_obj.name,
                document_type=file_obj.name.split(".")[-1].lower(),
                file=file_obj,
            )
            process_document.delay(workflow.id)

    @action(detail=True, methods=["patch"])
    def submit(self, request, pk=None):
        workflow = self.get_object()
        WorkflowService.submit_workflow(workflow)
        publish_workflow_created(
            workflow_id=workflow.id,
            submitter_id=workflow.created_by_id,
            deadline=workflow.deadline.isoformat() if workflow.deadline else None,
            correlation_id=getattr(request, "correlation_id", str(uuid.uuid4())),
        )
        return response.Response(WorkflowSerializer(workflow).data)

    @action(detail=False, methods=["post"], url_path="csv-dry-run")
    def csv_dry_run(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return response.Response({"detail": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST)
        text = csv_file.read().decode("utf-8")
        rows = [line for line in text.splitlines() if line.strip()]
        errors = []
        if rows and "name" not in rows[0].lower():
            errors.append("Missing required column: name")

        key = f"csv_preview:{request.user.id}:{uuid.uuid4()}"
        cache.set(key, rows[:20], 1800)
        job = CSVImportJob.objects.create(created_by_id=request.user.id, status="validated", preview_cache_key=key)
        return response.Response({"job_id": job.id, "valid_rows": max(len(rows) - 1, 0), "errors": errors})

    @action(detail=False, methods=["post"], url_path="csv-process")
    def csv_process(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return response.Response({"detail": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST)
        text = csv_file.read().decode("utf-8")
        task = process_csv_bulk.delay(text, request.user.id)
        return response.Response({"task_id": task.id, "status": "processing"}, status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    checks = {"database": "error", "cache": "error"}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        pass

    try:
        cache.set("health", "ok", 10)
        checks["cache"] = "ok"
    except Exception:
        pass

    healthy = all(value == "ok" for value in checks.values())
    return response.Response(
        {"status": "healthy" if healthy else "unhealthy", **checks},
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
