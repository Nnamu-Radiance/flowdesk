from django.db import models


class ApprovalChain(models.Model):
    workflow_id = models.IntegerField(db_index=True)
    workflow_type = models.CharField(max_length=120, blank=True)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class ApprovalStep(models.Model):
    chain = models.ForeignKey(ApprovalChain, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveIntegerField()
    approver_id = models.IntegerField(db_index=True)
    role_required = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, default="pending", db_index=True)

    class Meta:
        unique_together = [("chain", "order")]
        ordering = ["order"]


class ApprovalRecord(models.Model):
    workflow_id = models.IntegerField(db_index=True)
    approver_id = models.IntegerField(db_index=True)
    action = models.CharField(max_length=20)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
