from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_SUBMITTER = "submitter"
    ROLE_APPROVER = "approver"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_SUBMITTER, "Submitter"),
        (ROLE_APPROVER, "Approver"),
        (ROLE_ADMIN, "Admin"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_SUBMITTER, db_index=True)
    department = models.CharField(max_length=120, blank=True)
    notification_preferences = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return self.get_full_name() or self.username
