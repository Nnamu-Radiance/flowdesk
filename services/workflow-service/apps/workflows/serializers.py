from rest_framework import serializers

from apps.workflows.models import Document, Workflow, WorkflowType


class WorkflowTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowType
        fields = [
            "id",
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
            "created_at",
            "updated_at",
        ]


class DocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "doc_id",
            "document_label",
            "filename",
            "document_type",
            "url",
            "extracted_text",
            "embedding",
            "uploaded_at",
            "created_at",
        ]

    def get_url(self, document):
        return document.file.url if document.file else ""


class WorkflowSerializer(serializers.ModelSerializer):
    workflow_type_detail = WorkflowTypeSerializer(source="workflow_type", read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    document = serializers.SerializerMethodField()
    remaining_time = serializers.CharField(read_only=True)
    sla_percentage = serializers.IntegerField(read_only=True)

    class Meta:
        model = Workflow
        fields = [
            "id",
            "workflow_type",
            "workflow_type_detail",
            "name",
            "description",
            "approval_type",
            "status",
            "sla_status",
            "created_by_id",
            "assigned_to_id",
            "student_name",
            "student_matricule",
            "student_faculty",
            "form_data",
            "deadline",
            "submitted_at",
            "priority",
            "tags",
            "metadata",
            "all_documents_required",
            "appeal_round",
            "created_at",
            "documents",
            "document",
            "remaining_time",
            "sla_percentage",
        ]
        read_only_fields = [
            "id",
            "name",
            "status",
            "sla_status",
            "created_by_id",
            "deadline",
            "submitted_at",
            "appeal_round",
            "created_at",
        ]

    def get_document(self, workflow):
        document = workflow.documents.first()
        return DocumentSerializer(document, context=self.context).data if document else None
