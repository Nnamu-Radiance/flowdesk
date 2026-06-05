from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.workflows.permissions import CanEditWorkflow
from apps.workflows.serializers import WorkflowDetailSerializer, WorkflowSerializer
from apps.workflows.services import WorkflowRepository
from apps.workflows.tasks import process_csv_bulk, process_workflow_document
from apps.workflows.csv_import import parse_workflow_csv


def serialize_csv_preview_row(row):
    approval_type = row.get("approval_type")
    if hasattr(approval_type, "name"):
        approval_type = approval_type.name
    deadline = row.get("deadline")
    return {
        **row,
        "approval_type": approval_type or "",
        "deadline": deadline.isoformat() if deadline else None,
    }


@action(detail=False, methods=["post"], url_path="csv-dry-run")
def csv_dry_run(self, request):
    if "file" not in request.FILES:
        return Response({"error": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST)

    result = parse_workflow_csv(request.FILES["file"].read().decode("utf-8"))
    return Response({
        "valid_rows": len(result.valid_rows),
        "invalid_rows": result.invalid_rows,
        "errors": result.errors[:20],
        "preview": [serialize_csv_preview_row(row) for row in result.valid_rows[:10]],
    })


@action(detail=False, methods=["post"], url_path="csv-process")
def csv_process(self, request):
    if "file" not in request.FILES:
        return Response({"error": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST)

    content = request.FILES["file"].read().decode("utf-8")
    task = process_csv_bulk.delay(content, request.user.id)
    return Response({"task_id": task.id, "status": "processing"}, status=status.HTTP_202_ACCEPTED)


class WorkflowViewSet(viewsets.ModelViewSet):
    serializer_class = WorkflowSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "assigned_to"]
    search_fields = ["name", "document__filename"]
    ordering_fields = ["created_at", "deadline"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return WorkflowRepository.get_visible_to_user(self.request.user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WorkflowDetailSerializer
        return WorkflowSerializer

    def perform_create(self, serializer):
        workflow = serializer.save(created_by=self.request.user)
        process_workflow_document.delay(workflow.id)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="csv-dry-run",
    )
    def csv_dry_run(self, request):
        if "file" not in request.FILES:
            return Response(
                {"error": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST
            )
        result = parse_workflow_csv(request.FILES["file"].read().decode("utf-8"))
        return Response({
            "valid_rows": len(result.valid_rows),
            "invalid_rows": result.invalid_rows,
            "errors": result.errors[:20],
            "preview": [serialize_csv_preview_row(row) for row in result.valid_rows[:10]],
        })

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="csv-process",
    )
    def csv_process(self, request):
        if "file" not in request.FILES:
            return Response(
                {"error": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST
            )
        content = request.FILES["file"].read().decode("utf-8")
        task = process_csv_bulk.delay(content, request.user.id)
        return Response(
            {"task_id": task.id, "status": "processing"},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, CanEditWorkflow],
    )
    def submit(self, request, pk=None):
        workflow = self.get_object()
        workflow.submit(request.user)
        return Response({"status": "submitted"})
    
    @action(detail=False, methods=["post"], url_path="csv_dry_run")
    def csv_dry_run_legacy(self, request):
        return self.csv_dry_run(request)

    @action(detail=False, methods=["post"], url_path="csv_process")
    def csv_process_legacy(self, request):
        return self.csv_process(request)
