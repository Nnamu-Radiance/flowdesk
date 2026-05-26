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
    django_user_model.objects.create_user(username="admin", password="admin123", role="admin")
    client = APIClient()
    response = client.post(reverse("auth-login"), {"username": "admin", "password": "admin123"}, format="json")
    assert response.status_code == 200
    assert "access" in response.data


@pytest.mark.django_db
def test_user_endpoints(django_user_model):
    admin = django_user_model.objects.create_user(username="admin_user", password="password", role="admin")
    user = django_user_model.objects.create_user(username="testuser", password="password", role="submitter")
    client = APIClient()
    
    # Test Login
    login_res = client.post(reverse("auth-login"), {"username": "admin_user", "password": "password"})
    token = login_res.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Test Me
    response = client.get(reverse("auth-me"))
    assert response.status_code == 200
    assert response.data["username"] == "admin_user"

    # Test List
    response = client.get(reverse("auth-users-list"))
    assert response.status_code == 200
    assert len(response.data) >= 2

    # Test Update Role
    response = client.patch(reverse("auth-user-role", kwargs={"pk": user.pk}), {"role": "approver"})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.role == "approver"

    # Test Logout (mock)
    response = client.post(reverse("auth-logout"))
    assert response.status_code == 200

    # Test Refresh
    response = client.post(reverse("auth-refresh"), {"refresh": login_res.data["refresh"]})
    assert response.status_code == 200

