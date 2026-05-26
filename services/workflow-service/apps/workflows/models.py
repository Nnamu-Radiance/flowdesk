from django.db import models
from django.utils import timezone


class Workflow(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("in_approval", "In Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    SLA_STATUS_CHOICES = [
        ("on_track", "On Track"),
        ("warning_50", "50% Deadline"),
        ("warning_75", "75% Deadline"),
        ("overdue", "Overdue"),
    ]

    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    sla_status = models.CharField(max_length=20, choices=SLA_STATUS_CHOICES, default="on_track", db_index=True)
    created_by_id = models.IntegerField(db_index=True)
    assigned_to_id = models.IntegerField(null=True, blank=True, db_index=True)
    deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"]), models.Index(fields=["created_by_id", "status"])]

    @property
    def is_overdue(self) -> bool:
        return bool(self.deadline and timezone.now() > self.deadline and self.status != "approved")


class Document(models.Model):
    doc_id = models.CharField(max_length=64, unique=True, db_index=True)
    workflow = models.OneToOneField(Workflow, on_delete=models.CASCADE, related_name="document")
    filename = models.CharField(max_length=255)
    document_type = models.CharField(max_length=30)
    file = models.FileField(upload_to="documents/%Y/%m/%d/")
    extracted_text = models.TextField(blank=True)
    embedding = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CSVImportJob(models.Model):
    created_by_id = models.IntegerField()
    status = models.CharField(max_length=20, default="pending")
    preview_cache_key = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
