from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


DOCUMENT_LABELS = {
    "birth_certificate": "Birth Certificate",
    "o_level_certificate_certified": "Certified O-Level Certificate",
    "a_level_certificate_certified": "Certified A-Level Certificate",
    "authentication_payment_receipt": "Authentication Payment Receipt",
    "transcript": "Academic Transcript",
    "final_year_project": "Final Year Project",
    "project_description": "Project Description",
    "internship_evaluation_form": "Internship Evaluation Form",
    "internship_report": "Internship Report",
}


def label_for_document_slug(slug: str) -> str:
    return DOCUMENT_LABELS.get(slug, slug.replace("_", " ").title())


class Workflow(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        IN_APPROVAL = "in_approval", "In Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", "Returned for Changes"

    class SLAStatus(models.TextChoices):
        ON_TRACK = "on_track", "On Track"
        WARNING_50 = "warning_50", "Warning (50%)"
        WARNING_75 = "warning_75", "Warning (75%)"
        OVERDUE = "overdue", "Overdue"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("in_approval", "In Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("returned", "Returned for Changes"),
    ]

    SLA_STATUS_CHOICES = [
        ("on_track", "On Track"),
        ("warning_50", "50% Deadline"),
        ("warning_75", "75% Deadline"),
        ("overdue", "Overdue"),
    ]

    workflow_type = models.ForeignKey(
        "WorkflowType",
        on_delete=models.PROTECT,
        related_name="workflows",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    approval_type = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=Status.DRAFT, db_index=True)
    sla_status = models.CharField(max_length=20, choices=SLA_STATUS_CHOICES, default=SLAStatus.ON_TRACK, db_index=True)
    created_by_id = models.IntegerField(db_index=True)
    assigned_to_id = models.IntegerField(null=True, blank=True, db_index=True)
    student_name = models.CharField(max_length=200, blank=True)
    student_matricule = models.CharField(max_length=50, blank=True)
    student_faculty = models.CharField(max_length=200, blank=True)
    form_data = models.JSONField(default=dict, blank=True)
    deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=1)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    all_documents_required = models.BooleanField(default=False)
    appeal_round = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"]), models.Index(fields=["created_by_id", "status"])]

    @property
    def is_overdue(self) -> bool:
        return bool(self.deadline and timezone.now() > self.deadline and self.status != "approved")

    @property
    def sla_percentage(self):
        if not self.submitted_at or not self.deadline:
            return 0
        total = (self.deadline - self.submitted_at).total_seconds()
        elapsed = (timezone.now() - self.submitted_at).total_seconds()
        return min(int((elapsed / total) * 100), 100) if total > 0 else 100

    @property
    def remaining_time(self):
        if not self.deadline:
            return "No deadline"
        delta = self.deadline - timezone.now()
        if delta.total_seconds() <= 0:
            return "Overdue"
        days = delta.days
        hours = delta.seconds // 3600
        if days > 0:
            return f"{days}d {hours}h"
        return f"{hours}h remaining"

    def update_sla_status(self):
        pct = self.sla_percentage
        if pct >= 100:
            self.sla_status = self.SLAStatus.OVERDUE
        elif pct >= 75:
            self.sla_status = self.SLAStatus.WARNING_75
        elif pct >= 50:
            self.sla_status = self.SLAStatus.WARNING_50
        else:
            self.sla_status = self.SLAStatus.ON_TRACK


class WorkflowType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    approval_type = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    department = models.CharField(max_length=200, blank=True)
    priority = models.PositiveSmallIntegerField(default=2)
    tags = models.JSONField(default=list, blank=True)
    required_docs = models.JSONField(default=list, blank=True)
    form_fields = models.JSONField(default=list, blank=True)
    approval_chain = models.JSONField(default=list, blank=True)
    all_documents_required = models.BooleanField(default=True)
    expected_output = models.TextField(blank=True)
    sla_days = models.PositiveIntegerField(default=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkflowConfigUpload(models.Model):
    uploaded_by_id = models.IntegerField()
    file = models.FileField(upload_to="workflow_config/%Y/%m/%d/")
    created = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]


class Document(models.Model):
    doc_id = models.CharField(max_length=64, unique=True, db_index=True)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="documents")
    document_label = models.CharField(max_length=200, blank=True)
    filename = models.CharField(max_length=300)
    document_type = models.CharField(max_length=30)
    file = models.FileField(upload_to="workflow_docs/%Y/%m/%d/")
    extracted_text = models.TextField(blank=True)
    embedding = models.JSONField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ApprovalStop(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_review", "In Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="approval_stops")
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("workflow", "order")]

    def clean(self):
        super().clean()
        if self.status not in {"in_review", "approved"}:
            return

        from apps.workflows.services import check_document_completeness

        complete, missing_labels = check_document_completeness(self.workflow)
        if not complete:
            raise ValidationError(
                f"Cannot process: missing required documents: {missing_labels}"
            )

        if self.status == "approved":
            previous_pending = self.workflow.approval_stops.filter(
                order__lt=self.order,
            ).exclude(status="approved")
            if self.pk:
                previous_pending = previous_pending.exclude(pk=self.pk)
            if previous_pending.exists():
                raise ValidationError("Cannot approve: previous approval stops are not approved")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.status == "in_review" and not self.started_at:
            self.started_at = timezone.now()
        if self.status == "approved" and not self.approved_at:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)


class WorkflowDocumentRequirement(models.Model):
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="document_requirements")
    document_slug = models.CharField(max_length=120)
    label = models.CharField(max_length=255, blank=True)
    is_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("workflow", "document_slug")]
        ordering = ["id"]

    def save(self, *args, **kwargs):
        if not self.label:
            self.label = label_for_document_slug(self.document_slug)
        super().save(*args, **kwargs)


class WorkflowDocumentUpload(models.Model):
    workflow_instance = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="document_uploads")
    requirement = models.ForeignKey(
        WorkflowDocumentRequirement,
        on_delete=models.CASCADE,
        related_name="uploads",
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    file = models.FileField(upload_to="workflow-requirements/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["workflow_instance", "requirement"]),
            models.Index(fields=["verified"]),
        ]


class CSVImportJob(models.Model):
    created_by_id = models.IntegerField()
    status = models.CharField(max_length=20, default="pending")
    preview_cache_key = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
