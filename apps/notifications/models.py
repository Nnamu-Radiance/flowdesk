from django.conf import settings
from django.db import models


class Notification(models.Model):
    TYPE_CHOICES = [
        ("info", "Info"),
        ("approval", "Approval"),
        ("sla", "SLA"),
        ("error", "Error"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default="info"
    )
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Subscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_subscription",
    )
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
