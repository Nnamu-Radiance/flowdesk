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
    response = client.get(reverse("auth-users"))
    assert response.status_code == 200
    assert len(response.data) >= 2

    # Test Create User
    new_user_data = {
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123",
        "role": "submitter"
    }
    response = client.post(reverse("auth-users"), new_user_data)
    assert response.status_code == 201
    assert django_user_model.objects.filter(username="newuser").exists()

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


@pytest.mark.django_db
def test_jwt_local_authentication(django_user_model, monkeypatch, settings):
    from apps.auth.authentication import JWTLocalAuthentication
    from rest_framework_simplejwt.tokens import AccessToken
    from rest_framework.exceptions import AuthenticationFailed

    # Ensure JWT secret is configured for shared validator
    monkeypatch.setenv("JWT_SECRET_KEY", settings.SECRET_KEY)

    user = django_user_model.objects.create_user(username="jwt_user", role="submitter")
    auth = JWTLocalAuthentication()

    # Test missing header
    request = type("Request", (), {"headers": {}})
    assert auth.authenticate(request) is None

    # Test invalid header
    request = type("Request", (), {"headers": {"Authorization": "Basic 123"}})
    assert auth.authenticate(request) is None

    # Test valid token
    token = str(AccessToken.for_user(user))
    request = type("Request", (), {"headers": {"Authorization": f"Bearer {token}"}})
    authenticated_user, payload = auth.authenticate(request)
    assert authenticated_user.id == user.id
    assert authenticated_user.role == "submitter"
    assert authenticated_user.is_authenticated is True

    # Test invalid token
    request = type("Request", (), {"headers": {"Authorization": "Bearer invalid-token"}})
    with pytest.raises(AuthenticationFailed):
        auth.authenticate(request)


def test_permissions():
    from apps.auth.permissions import IsAdmin, IsApprover, IsSubmitter

    admin = type("User", (), {"is_authenticated": True, "role": "admin"})
    approver = type("User", (), {"is_authenticated": True, "role": "approver"})
    submitter = type("User", (), {"is_authenticated": True, "role": "submitter"})
    anon = type("User", (), {"is_authenticated": False, "role": "guest"})

    # IsAdmin
    p = IsAdmin()
    assert p.has_permission(type("Req", (), {"user": admin}), None) is True
    assert p.has_permission(type("Req", (), {"user": approver}), None) is False
    assert p.has_permission(type("Req", (), {"user": anon}), None) is False

    # IsApprover
    p = IsApprover()
    assert p.has_permission(type("Req", (), {"user": admin}), None) is True
    assert p.has_permission(type("Req", (), {"user": approver}), None) is True
    assert p.has_permission(type("Req", (), {"user": submitter}), None) is False

    # IsSubmitter
    p = IsSubmitter()
    assert p.has_permission(type("Req", (), {"user": submitter}), None) is True
    assert p.has_permission(type("Req", (), {"user": anon}), None) is False

