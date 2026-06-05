from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.views.generic import RedirectView
from django_prometheus.exports import ExportToDjangoView
from rest_framework.routers import DefaultRouter
from apps.approvals.views import ApprovalViewSet
from apps.workflows.views import WorkflowViewSet
from apps.approvals.admin_views import (
    AdminUserViewSet,
    ApprovalChainAdminViewSet,
    ApprovalTypeAdminViewSet,
)

admin_router = DefaultRouter()
admin_router.register("approval-types", ApprovalTypeAdminViewSet, basename="admin-approval-types")
admin_router.register("approval-chains", ApprovalChainAdminViewSet, basename="admin-approval-chains")
admin_router.register("users", AdminUserViewSet, basename="admin-users")

router = DefaultRouter()
router.register("workflows", WorkflowViewSet, basename="workflows")
router.register("approvals", ApprovalViewSet, basename="approvals")

urlpatterns = [
    path("", RedirectView.as_view(url="/static/pages/dashboard.html", permanent=False)),
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}images/logo.svg", permanent=True)),
    path("login/", RedirectView.as_view(url="/static/login.html", permanent=False)),
    path("workflows/", RedirectView.as_view(url="/static/pages/workflows.html", permanent=False)),
    path("approvals/pending/", RedirectView.as_view(url="/static/pages/approvals.html", permanent=False)),
    path("analytics/", RedirectView.as_view(url="/static/pages/analytics.html", permanent=False)),
    path("admin/config/", RedirectView.as_view(url="/static/pages/admin-config.html", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.auth.urls")),
    path("api/analytics/", include("apps.analytics.urls")),
    path("api/", include(router.urls)),
    path("metrics/", ExportToDjangoView, name="prometheus-django-metrics"),
    path("api/admin/", include(admin_router.urls)),
]