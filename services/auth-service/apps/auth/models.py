from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        SUBMITTER = "submitter", "Submitter"
        APPROVER = "approver", "Approver"
        ADMIN = "admin", "Admin"

    class ApproverType(models.TextChoices):
        # Institutional roles — identified by title
        REGISTRAR = "registrar", "Registrar"
        DEAN = "dean", "Dean"
        HOD = "hod", "Head of Department"
        ADMIN_ASSISTANT = "admin_assistant", "Administrative Assistant"
        FACULTY_COUNCIL = "faculty_council", "Faculty Scientific Council"
        DVC = "dvc", "Deputy Vice Chancellor"
        # Personal role — identified by name
        SUPERVISOR = "supervisor", "Supervisor"

    ROLE_SUBMITTER = Role.SUBMITTER
    ROLE_APPROVER = Role.APPROVER
    ROLE_ADMIN = Role.ADMIN
    ROLE_CHOICES = Role.choices

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.SUBMITTER,
        db_index=True,
    )
    # Only populated when role == 'approver'
    # Null for submitters and admins
    approver_type = models.CharField(
        max_length=30,
        choices=ApproverType.choices,
        null=True,
        blank=True,
        db_index=True,
    )

    full_name = models.CharField(max_length=200, blank=True)
    matricule = models.CharField(max_length=50, blank=True, unique=True, null=True)
    faculty = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to="profiles/", null=True, blank=True)
    signature_image = models.ImageField(upload_to="signatures/", null=True, blank=True)
    stamp_image = models.ImageField(upload_to="stamps/", null=True, blank=True)
    google_id = models.CharField(max_length=200, blank=True, null=True, unique=True)
    notification_preferences = models.JSONField(default=dict, blank=True)

    def is_approver(self):
        return self.role == self.Role.APPROVER

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_supervisor(self):
        return self.role == self.Role.APPROVER and self.approver_type == self.ApproverType.SUPERVISOR

    def display_role(self):
        """Human-readable role shown in the UI and emails."""
        if self.role == self.Role.APPROVER and self.approver_type:
            return self.get_approver_type_display()
        return self.get_role_display()

    def __str__(self):
        return self.full_name or self.get_full_name() or self.username


class RoleChangeLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_changes")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="role_changes_made")
    old_role = models.CharField(max_length=20)
    new_role = models.CharField(max_length=20)
    old_approver_type = models.CharField(max_length=30, blank=True)
    new_approver_type = models.CharField(max_length=30, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
