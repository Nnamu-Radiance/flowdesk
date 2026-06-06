import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework import exceptions
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
        "/api/analytics/workflow-volume/",
        "/api/analytics/approver-performance/",
        "/api/analytics/rejection-rates/",
    ]
    for url in endpoints:
        response = api_client.get(url)
        assert response.status_code == 200


def test_jwt_authentication_missing_header_returns_none():
    from apps.analytics.authentication import JWTLocalAuthentication

    auth = JWTLocalAuthentication()
    request = RequestFactory().get("/")

    assert auth.authenticate(request) is None


def test_jwt_authentication_valid_token(monkeypatch):
    from apps.analytics.authentication import JWTLocalAuthentication, ServiceUser

    monkeypatch.setattr(
        "apps.analytics.authentication.validate_jwt",
        lambda token: {"user_id": 77, "role": "approver"},
    )

    auth = JWTLocalAuthentication()
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer token")

    user, payload = auth.authenticate(request)
    assert isinstance(user, ServiceUser)
    assert user.id == 77
    assert user.role == "approver"
    assert payload["user_id"] == 77


def test_jwt_authentication_invalid_token_raises(monkeypatch):
    from apps.analytics.authentication import JWTLocalAuthentication

    def _boom(_token):
        raise Exception("invalid")

    monkeypatch.setattr("apps.analytics.authentication.validate_jwt", _boom)

    auth = JWTLocalAuthentication()
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer bad-token")

    with pytest.raises(exceptions.AuthenticationFailed):
        auth.authenticate(request)


def test_service_user_is_authenticated_property():
    from apps.analytics.authentication import ServiceUser

    user = ServiceUser(user_id=9, role="admin")
    assert user.is_authenticated is True


def test_correlation_id_middleware_propagates_header():
    from apps.analytics.middleware import CorrelationIdMiddleware

    request = RequestFactory().get("/", HTTP_X_CORRELATION_ID="corr-123")
    middleware = CorrelationIdMiddleware(lambda req: HttpResponse("ok"))

    response = middleware(request)
    assert request.correlation_id == "corr-123"
    assert response["X-Correlation-ID"] == "corr-123"


def test_analytics_service_cached_payload_uses_cache():
    from django.core.cache import cache

    from apps.analytics.services import AnalyticsService

    cache.clear()
    calls = {"count": 0}

    def compute():
        calls["count"] += 1
        return {"value": 123}

    first = AnalyticsService.cached_payload("analytics:test-key", compute, ttl=60)
    second = AnalyticsService.cached_payload("analytics:test-key", compute, ttl=60)

    assert first == {"value": 123}
    assert second == {"value": 123}
    assert calls["count"] == 1


def test_generate_daily_reports_task_returns_queued():
    from apps.analytics.tasks import generate_daily_reports

    assert generate_daily_reports() == {"status": "queued"}


def test_serializers_accept_valid_payloads():
    from apps.analytics.serializers import DashboardSerializer, MetricItemSerializer

    dashboard = DashboardSerializer(
        data={
            "total_workflows": 10,
            "approved": 6,
            "rejected": 1,
            "pending": 3,
        }
    )
    metric = MetricItemSerializer(data={"label": "Ops", "value": 98.5})

    assert dashboard.is_valid(), dashboard.errors
    assert metric.is_valid(), metric.errors
