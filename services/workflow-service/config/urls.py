from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django_prometheus.exports import ExportToDjangoView

from apps.workflows.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check),
    path("metrics/", ExportToDjangoView, name="prometheus-django-metrics"),
    path("api/workflows/", include("apps.workflows.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
