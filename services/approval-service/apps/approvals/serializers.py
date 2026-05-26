from rest_framework import serializers

from apps.approvals.models import ApprovalChain, ApprovalRecord, ApprovalStep


class ApprovalStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalStep
        fields = ["id", "order", "approver_id", "role_required", "status"]


class ApprovalChainSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True, read_only=True)

    class Meta:
        model = ApprovalChain
        fields = ["id", "workflow_id", "workflow_type", "name", "steps", "created_at"]


class ApprovalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRecord
        fields = ["id", "workflow_id", "approver_id", "action", "comments", "created_at"]
