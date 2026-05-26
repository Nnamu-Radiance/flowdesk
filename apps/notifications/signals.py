from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.tasks import send_approval_notification
from apps.workflows.models import Workflow


@receiver(post_save, sender=Workflow)
def notify_on_assignment(sender, instance, **kwargs):
    if instance.assigned_to_id and instance.status == "in_approval":
        send_approval_notification.delay(instance.id, instance.assigned_to_id)
