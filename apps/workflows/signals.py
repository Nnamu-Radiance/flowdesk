from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.approvals.services import ApprovalService
from apps.workflows.models import Workflow


@receiver(post_save, sender=Workflow)
def route_submitted_workflow(sender, instance: Workflow, created: bool, **kwargs):
    if instance.status == "submitted" and not instance.assigned_to_id:
        ApprovalService.auto_route_workflow(instance)
