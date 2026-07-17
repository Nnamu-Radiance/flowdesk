from django.db import models

RETURNED_FOR_CHANGES_LABEL = "Returned for Changes"


class LegacyAliasQuerySet(models.QuerySet):
    field_aliases = {}

    def _alias_field(self, field):
        descending = isinstance(field, str) and field.startswith("-")
        raw = field[1:] if descending else field
        aliased = self.field_aliases.get(raw, raw)
        return f"-{aliased}" if descending else aliased

    def _alias_kwargs(self, kwargs):
        aliased = {}
        for key, value in kwargs.items():
            parts = key.split("__", 1)
            field = self.field_aliases.get(parts[0], parts[0])
            aliased["__".join([field, parts[1]]) if len(parts) > 1 else field] = value
        return aliased

    def filter(self, *args, **kwargs):
        return super().filter(*args, **self._alias_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **self._alias_kwargs(kwargs))

    def order_by(self, *field_names):
        return super().order_by(*(self._alias_field(field) for field in field_names))

    def values_list(self, *fields, **kwargs):
        return super().values_list(*(self._alias_field(field) for field in fields), **kwargs)


class ApprovalStepQuerySet(LegacyAliasQuerySet):
    field_aliases = {"order": "step_number", "approver_id": "assignee_id"}


class ApprovalRecordQuerySet(LegacyAliasQuerySet):
    field_aliases = {"approver_id": "actor_id"}


class ApprovalChain(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", RETURNED_FOR_CHANGES_LABEL

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
        if hasattr(self, "_legacy_name"):
            return self._legacy_name
        if self.workflow_type_name:
            return f"{self.workflow_type_name} Approval Chain"
        return "Default Chain"

    @name.setter
    def name(self, value):
        self._legacy_name = value
        if value and value != "Default Chain" and not self.workflow_type_name:
            self.workflow_type_name = str(value).replace(" Approval Chain", "")


class ApprovalStep(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", RETURNED_FOR_CHANGES_LABEL
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

    objects = ApprovalStepQuerySet.as_manager()

    class Meta:
        unique_together = [("chain", "step_number")]
        ordering = ["step_number"]

    @property
    def order(self):
        return self.step_number

    @order.setter
    def order(self, value):
        self.step_number = value

    @property
    def approver_id(self):
        return self.assignee_id

    @approver_id.setter
    def approver_id(self, value):
        self.assignee_id = value


class ApprovalRecord(models.Model):
    class Action(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", RETURNED_FOR_CHANGES_LABEL
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

    objects = ApprovalRecordQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]

    @property
    def approver_id(self):
        return self.actor_id
