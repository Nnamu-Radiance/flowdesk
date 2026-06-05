from django.contrib import admin
from django.urls import include, path
from django_prometheus.exports import ExportToDjangoView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.analytics.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check),
    path("metrics/", ExportToDjangoView, name="prometheus-django-metrics"),
    path("api/analytics/", include("apps.analytics.urls")),
    # OpenAPI Schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Swagger UI
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # Redoc UI
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
