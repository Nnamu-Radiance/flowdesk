from django.contrib import admin
from django.urls import include, path

from apps.notifications.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check),
    path("metrics/", include("django_prometheus.urls")),
]
