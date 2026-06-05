from django.db import models


class ApprovalChain(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", "Returned for Changes"

    workflow_id = models.IntegerField(unique=True, db_index=True)
    workflow_type_name = models.CharField(max_length=200, blank=True)
    student_id = models.IntegerField(null=True, blank=True, db_index=True)
    student_name = models.CharField(max_length=200, blank=True)
    student_matricule = models.CharField(max_length=50, blank=True)
    student_faculty = models.CharField(max_length=200, blank=True)
    total_steps = models.PositiveIntegerField(default=0)
    current_step_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    deadline = models.DateTimeField(null=True, blank=True)
    documents = models.JSONField(default=list, blank=True)
    appeal_round = models.IntegerField(default=0)
    appeal_reason = models.TextField(blank=True, default="")
    original_rejection_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def workflow_type(self):
        return self.workflow_type_name

    @property
    def name(self):
        return f"{self.workflow_type_name or 'Workflow'} Approval Chain"


class ApprovalStep(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", "Returned for Changes"
        REASSIGNED = "reassigned", "Reassigned"
        VOID = "void", "Void"

    chain = models.ForeignKey(ApprovalChain, on_delete=models.CASCADE, related_name="steps")
    step_number = models.PositiveIntegerField()
    role_required = models.CharField(max_length=100)
    role_display_name = models.CharField(max_length=200)
    assignee_id = models.IntegerField(null=True, blank=True, db_index=True)
    assignee_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    comments = models.TextField(blank=True)
    has_annotated_document = models.BooleanField(default=False)

    class Meta:
        unique_together = [("chain", "step_number")]
        ordering = ["step_number"]

    @property
    def order(self):
        return self.step_number

    @property
    def approver_id(self):
        return self.assignee_id


class ApprovalRecord(models.Model):
    class Action(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", "Returned for Changes"
        REASSIGNED = "reassigned", "Reassigned"
        COMMENTED = "commented", "Commented"

    workflow_id = models.IntegerField(db_index=True)
    step_number = models.PositiveIntegerField()
    actor_id = models.IntegerField(db_index=True)
    actor_name = models.CharField(max_length=200, blank=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    comments = models.TextField(blank=True)
    annotated_document = models.FileField(upload_to="annotated_docs/%Y/%m/%d/", null=True, blank=True)
    approver_comments = models.TextField(blank=True, default="")
    comments_json = models.JSONField(default=list, blank=True)
    approver_signature_url = models.URLField(blank=True, default="")
    approver_stamp_url = models.URLField(blank=True, default="")
    send_to_submitter = models.BooleanField(default=False)
    send_feedback_to_student = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    @property
    def approver_id(self):
        return self.actor_id
