import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/health/")
    assert response.status_code in {200, 503}


@pytest.mark.django_db
def test_login_endpoint_exists(django_user_model):
    django_user_model.objects.create_user(username="admin", password="admin123")
    client = APIClient()
    response = client.post(reverse("auth-login"), {"username": "admin", "password": "admin123"}, format="json")
    assert response.status_code == 200
    assert "access" in response.data
