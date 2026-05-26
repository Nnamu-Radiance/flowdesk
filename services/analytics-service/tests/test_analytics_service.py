import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    from apps.analytics.authentication import ServiceUser
    client = APIClient()
    user = ServiceUser(user_id=1, role="admin")
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/health/")
    assert response.status_code in {200, 503}


@pytest.mark.django_db
def test_analytics_views(api_client):
    endpoints = [
        "/api/analytics/dashboard/",
        "/api/analytics/sla-report/",
        "/api/analytics/volume/",
        "/api/analytics/approver-performance/",
    ]
    for url in endpoints:
        response = api_client.get(url)
        assert response.status_code == 200
