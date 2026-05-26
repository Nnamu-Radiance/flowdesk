from django.urls import path

from apps.approvals.views import (
    ApprovalDecisionView,
    HistoryView,
    PendingApprovalsView,
    ReassignView,
)

urlpatterns = [
    path("pending/", PendingApprovalsView.as_view(), name="approval-pending"),
    path("<int:chain_id>/approve/", ApprovalDecisionView.as_view(), {"action": "approve"}, name="approval-approve"),
    path("<int:chain_id>/reject/", ApprovalDecisionView.as_view(), {"action": "reject"}, name="approval-reject"),
    path("<int:chain_id>/reassign/", ReassignView.as_view(), name="approval-reassign"),
    path("<int:chain_id>/history/", HistoryView.as_view(), name="approval-history"),
]
