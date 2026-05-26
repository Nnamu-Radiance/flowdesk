from rest_framework import serializers

from apps.approvals.models import ApprovalRecord


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
