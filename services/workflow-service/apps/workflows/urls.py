from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.workflows.views import (
    WorkflowConfigDetailView,
    WorkflowConfigListView,
    WorkflowConfigUploadView,
    WorkflowViewSet,
)

router = DefaultRouter()
router.register("", WorkflowViewSet, basename="workflow")

urlpatterns = [
    path("config/upload/", WorkflowConfigUploadView.as_view(), name="workflow-config-upload"),
    path("config/<int:pk>/", WorkflowConfigDetailView.as_view(), name="workflow-config-detail"),
    path("config/", WorkflowConfigListView.as_view(), name="workflow-config-list"),
    path("", include(router.urls)),
]