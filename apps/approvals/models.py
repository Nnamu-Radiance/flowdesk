from django.conf import settings
from django.db import models


class ApprovalType(models.Model):
    name = models.CharField(max_length=120, unique=True)
    sla_hours = models.PositiveIntegerField(default=48)

    def __str__(self):
        return self.name


class ApprovalChain(models.Model):
    workflow_type = models.ForeignKey(
        ApprovalType, on_delete=models.CASCADE, related_name="chains"
    )
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.name


class ApprovalStep(models.Model):
    chain = models.ForeignKey(
        ApprovalChain, on_delete=models.CASCADE, related_name="steps"
    )
    order = models.PositiveIntegerField()
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role_required = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("chain", "order")]


class ApprovalRecord(models.Model):
    ACTION_CHOICES = [
        ("approve", "Approve"),
        ("reject", "Reject"),
        ("reassign", "Reassign"),
    ]

    workflow = models.ForeignKey(
        "workflows.Workflow", on_delete=models.CASCADE, related_name="approval_records"
    )
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    comments = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workflow", "-created_at"])]
