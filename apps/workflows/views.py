from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.workflows.permissions import CanEditWorkflow
from apps.workflows.serializers import WorkflowDetailSerializer, WorkflowSerializer
from apps.workflows.services import WorkflowRepository
from apps.workflows.tasks import process_csv_bulk, process_workflow_document


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
        detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def csv_dry_run(self, request):
        if "file" not in request.FILES:
            return Response(
                {"error": "CSV file required"}, status=status.HTTP_400_BAD_REQUEST
            )
        content = request.FILES["file"].read().decode("utf-8")
        rows = [line for line in content.splitlines() if line.strip()]
        valid_rows = max(len(rows) - 1, 0)
        return Response({"valid_rows": valid_rows, "invalid_rows": 0, "errors": []})

    @action(
        detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated]
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
