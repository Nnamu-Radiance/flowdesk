from rest_framework import serializers
from apps.approvals.models import ApprovalChain, ApprovalStep, ApprovalType
from apps.auth.serializers import UserSerializer
from apps.approvals.models import ApprovalRecord

class ApprovalTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalType
        fields = ["id", "name", "sla_hours"]


class ApprovalStepWriteSerializer(serializers.Serializer):
    order = serializers.IntegerField(min_value=1)
    approver = serializers.IntegerField()
    role_required = serializers.CharField(required=False, allow_blank=True, max_length=40)


class ApprovalStepSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source="approver.get_full_name", read_only=True)

    class Meta:
        model = ApprovalStep
        fields = ["id", "order", "approver", "approver_name", "role_required"]


class ApprovalChainSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True, read_only=True)

    class Meta:
        model = ApprovalChain
        fields = ["id", "workflow_type", "name", "steps"]
        
class ApprovalRecordSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(
        source="approver.get_full_name", read_only=True
    )

    class Meta:
        model = ApprovalRecord
        fields = [
            "id",
            "workflow",
            "approver",
            "approver_name",
            "action",
            "comments",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "approver", "created_at"]
