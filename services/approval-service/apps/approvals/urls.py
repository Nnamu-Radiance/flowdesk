from django.urls import path

from apps.approvals.views import (
    ApprovalDecisionView,
    ApprovalDocumentsView,
    HistoryView,
    LegacyApprovalDecisionView,
    LegacyHistoryView,
    LegacyReassignView,
    PendingApprovalsView,
    ReassignView,
)

urlpatterns = [
    path("pending/", PendingApprovalsView.as_view(), name="approval-pending"),
    path("<int:workflow_id>/documents/", ApprovalDocumentsView.as_view(), name="approval-documents"),
    path("<int:workflow_id>/decide/", ApprovalDecisionView.as_view(), name="approval-decide"),
    path("<int:workflow_id>/reassign/", ReassignView.as_view(), name="approval-reassign"),
    path("<int:workflow_id>/history/", HistoryView.as_view(), name="approval-history"),
    path("chains/<int:chain_id>/approve/",
         LegacyApprovalDecisionView.as_view(),
         {"action": "approve"},
         name="approval-approve-legacy"),
    path("chains/<int:chain_id>/reject/",
         LegacyApprovalDecisionView.as_view(),
         {"action": "reject"},
         name="approval-reject-legacy"),
    path("chains/<int:chain_id>/reassign/", LegacyReassignView.as_view(), name="approval-reassign-legacy"),
    path("chains/<int:chain_id>/history/", LegacyHistoryView.as_view(), name="approval-history-legacy"),
]
