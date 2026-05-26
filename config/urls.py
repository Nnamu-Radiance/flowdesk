from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter

from apps.approvals.views import ApprovalViewSet
from apps.workflows.views import WorkflowViewSet

router = DefaultRouter()
router.register("workflows", WorkflowViewSet, basename="workflows")
router.register("approvals", ApprovalViewSet, basename="approvals")

urlpatterns = [
    path(
        "", TemplateView.as_view(template_name="pages/dashboard.html"), name="dashboard"
    ),
    path(
        "workflows/",
        TemplateView.as_view(template_name="pages/workflows_list.html"),
        name="workflows-page",
    ),
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.auth.urls")),
    path("api/analytics/", include("apps.analytics.urls")),
    path("api/", include(router.urls)),
    path("metrics/", include("django_prometheus.urls")),
]
