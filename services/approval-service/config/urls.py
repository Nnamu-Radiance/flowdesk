from django.contrib import admin
from django.urls import include, path
from django_prometheus.exports import ExportToDjangoView

from apps.approvals.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check),
    path("metrics/", ExportToDjangoView, name="prometheus-django-metrics"),
    path("api/approvals/", include("apps.approvals.urls")),
]
