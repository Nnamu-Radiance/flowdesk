from typing import Optional

from django.db import models

from apps.workflows.models import Workflow


class WorkflowRepository:
    @staticmethod
    def get_visible_to_user(user) -> models.QuerySet[Workflow]:
        queryset = Workflow.objects.select_related(
            "document", "created_by", "assigned_to", "approval_type"
        )
        if user.is_staff:
            return queryset
        return queryset.filter(models.Q(created_by=user) | models.Q(assigned_to=user))

    @staticmethod
    def get_pending_approvals(user) -> models.QuerySet[Workflow]:
        return WorkflowRepository.get_visible_to_user(user).filter(
            status="in_approval", assigned_to=user
        )

    @staticmethod
    def get_by_id_for_user(workflow_id: int, user) -> Optional[Workflow]:
        return (
            WorkflowRepository.get_visible_to_user(user).filter(id=workflow_id).first()
        )
