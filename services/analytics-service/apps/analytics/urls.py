from django.urls import path

from apps.analytics.views import (
    ApproverPerformanceView,
    DashboardView,
    SLAReportView,
    WorkflowVolumeView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="analytics-dashboard"),
    path("sla-report/", SLAReportView.as_view(), name="analytics-sla-report"),
    path("workflow-volume/", WorkflowVolumeView.as_view(), name="analytics-volume"),
    path("approver-performance/", ApproverPerformanceView.as_view(), name="analytics-approver-performance"),
]
