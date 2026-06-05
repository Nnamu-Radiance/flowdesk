from django.db import models


class Notification(models.Model):
    recipient_id = models.IntegerField(db_index=True)
    type = models.CharField(max_length=40, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    workflow_id = models.IntegerField(null=True, blank=True, db_index=True)
    read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    @property
    def is_read(self):
        return self.read


class Subscription(models.Model):
    user_id = models.IntegerField(unique=True)
    event_types = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
