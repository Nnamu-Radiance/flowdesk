from django.utils import timezone
from rest_framework import serializers

from apps.approvals.models import ApprovalChain, ApprovalRecord, ApprovalStep


class ApprovalStepSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(source="step_number", read_only=True)
    approver_id = serializers.IntegerField(source="assignee_id", read_only=True)

    class Meta:
        model = ApprovalStep
        fields = [
            "id",
            "step_number",
            "order",
            "role_required",
            "role_display_name",
            "assignee_id",
            "approver_id",
            "assignee_name",
            "status",
            "decision_at",
            "comments",
            "has_annotated_document",
        ]


class ApprovalChainSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True, read_only=True)
    workflow_type = serializers.CharField(source="workflow_type_name", read_only=True)
    name = serializers.CharField(read_only=True)
    sla_percentage = serializers.SerializerMethodField()
    remaining_time = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalChain
        fields = [
            "id",
            "workflow_id",
            "workflow_type",
            "workflow_type_name",
            "name",
            "student_id",
            "student_name",
            "student_matricule",
            "student_faculty",
            "total_steps",
            "current_step_number",
            "status",
            "deadline",
            "documents",
            "steps",
            "created_at",
            "sla_percentage",
            "remaining_time",
        ]

    def get_sla_percentage(self, chain):
        if not chain.deadline or not chain.created_at:
            return 0
        total = (chain.deadline - chain.created_at).total_seconds()
        if total <= 0:
            return 100
        used = (timezone.now() - chain.created_at).total_seconds()
        return min(round(used / total * 100, 1), 100)

    def get_remaining_time(self, chain):
        if not chain.deadline:
            return None
        delta = chain.deadline - timezone.now()
        if delta.total_seconds() <= 0:
            return "Overdue"
        days = delta.days
        hours = delta.seconds // 3600
        if days > 0:
            return f"{days}d {hours}h left"
        return f"{hours}h left"


class ApprovalRecordSerializer(serializers.ModelSerializer):
    approver_id = serializers.IntegerField(source="actor_id", read_only=True)
    annotated_document = serializers.FileField(read_only=True)
    annotated_document_url = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRecord
        fields = [
            "id",
            "workflow_id",
            "step_number",
            "actor_id",
            "approver_id",
            "actor_name",
            "action",
            "comments",
            "annotated_document",
            "annotated_document_url",
            "approver_comments",
            "send_to_submitter",
            "send_feedback_to_student",
            "created_at",
        ]

    def get_annotated_document_url(self, record):
        return record.annotated_document.url if record.annotated_document else ""
