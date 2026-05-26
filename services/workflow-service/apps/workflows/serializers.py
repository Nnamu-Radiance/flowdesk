from rest_framework import serializers

from apps.workflows.models import Document, Workflow


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["doc_id", "filename", "document_type", "extracted_text", "embedding", "created_at"]


class WorkflowSerializer(serializers.ModelSerializer):
    document = DocumentSerializer(read_only=True)

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "status",
            "sla_status",
            "created_by_id",
            "assigned_to_id",
            "deadline",
            "created_at",
            "document",
        ]
        read_only_fields = ["status", "sla_status", "created_by_id", "created_at"]
