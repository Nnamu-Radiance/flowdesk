from rest_framework import serializers

from apps.approvals.models import ApprovalRecord
from apps.workflows.models import Document, Workflow


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "doc_id",
            "filename",
            "document_type",
            "size_bytes",
            "extracted_text",
            "page_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "doc_id",
            "size_bytes",
            "extracted_text",
            "page_count",
            "created_at",
        ]


class WorkflowSerializer(serializers.ModelSerializer):
    document_preview = DocumentSerializer(source="document", read_only=True)

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "description",
            "status",
            "sla_status",
            "deadline",
            "created_at",
            "assigned_to",
            "approval_type",
            "document",
            "document_preview",
        ]
        read_only_fields = ["id", "status", "sla_status", "created_at", "assigned_to"]


class ApprovalRecordSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(
        source="approver.get_full_name", read_only=True
    )

    class Meta:
        model = ApprovalRecord
        fields = ["id", "action", "comments", "created_at", "approver_name"]


class WorkflowDetailSerializer(WorkflowSerializer):
    approval_history = ApprovalRecordSerializer(
        source="approval_records", many=True, read_only=True
    )

    class Meta(WorkflowSerializer.Meta):
        fields = WorkflowSerializer.Meta.fields + [
            "metadata",
            "priority",
            "approval_history",
        ]
