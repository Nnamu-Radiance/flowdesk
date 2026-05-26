from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.workflows.views import WorkflowViewSet

router = DefaultRouter()
router.register("", WorkflowViewSet, basename="workflow")

urlpatterns = [path("", include(router.urls))]
