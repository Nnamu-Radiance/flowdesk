from django.contrib import admin
from django.urls import include, path
from django.urls import path, include
from . import views

from apps.analytics.views import health_check

urlpatterns = [
    path('volume/', views.WorkflowVolumeView.as_view(), name='volume'),
    path("admin/", admin.site.urls),
    path("health/", health_check),
    path("metrics/", include("django_prometheus.urls")),
    path("api/analytics/", include("apps.analytics.urls")),
]
