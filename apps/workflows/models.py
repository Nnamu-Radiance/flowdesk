import hashlib
from datetime import timedelta

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class Document(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("pdf", "PDF"),
        ("docx", "Word"),
        ("xlsx", "Excel"),
        ("csv", "CSV"),
        ("image", "Image"),
    ]

    doc_id = models.CharField(max_length=50, unique=True, db_index=True, editable=False)
    filename = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=20, choices=DOCUMENT_TYPE_CHOICES, db_index=True
    )
    file = models.FileField(
        upload_to="documents/%Y/%m/%d/",
        validators=[
            FileExtensionValidator(["pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg"])
        ],
    )
    size_bytes = models.BigIntegerField(default=0)
    content_hash = models.CharField(max_length=64, unique=True)
    extracted_text = models.TextField(blank=True)
    embedding = models.JSONField(null=True, blank=True)
    page_count = models.IntegerField(null=True, blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.doc_id:
            ts = timezone.now().strftime("%Y%m%d%H%M%S")
            raw = f"{self.filename}:{ts}".encode("utf-8")
            self.doc_id = f"DOC-{ts}-{hashlib.sha1(raw).hexdigest()[:6].upper()}"
        if self.file and not self.size_bytes:
            self.size_bytes = self.file.size
        if self.filename and not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.filename.encode("utf-8")
            ).hexdigest()
        super().save(*args, **kwargs)

    def get_download_url(self) -> str:
        return self.file.url if self.file else ""


class Workflow(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("in_approval", "In Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("archived", "Archived"),
    ]

    SLA_STATUS_CHOICES = [
        ("on_track", "On Track"),
        ("warning_50", "50% Deadline"),
        ("warning_75", "75% Deadline"),
        ("overdue", "Overdue"),
    ]

    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    sla_status = models.CharField(
        max_length=20, choices=SLA_STATUS_CHOICES, default="on_track", db_index=True
    )
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="workflow",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workflows_created",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflows_assigned",
    )
    approval_type = models.ForeignKey(
        "approvals.ApprovalType",
        on_delete=models.PROTECT,
        related_name="workflows",
        null=True,
    )
    deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=1)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["deadline", "status"]),
        ]

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.deadline
            and self.status == "in_approval"
            and timezone.now() > self.deadline
        )

    @property
    def remaining_time(self):
        if not self.deadline:
            return None
        remaining = self.deadline - timezone.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def submit(self, submitter):
        if self.created_by_id != submitter.id:
            raise PermissionError("Only creator can submit")
        self.status = "submitted"
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "updated_at"])

    def __str__(self):
        return f"{self.name} ({self.status})"
