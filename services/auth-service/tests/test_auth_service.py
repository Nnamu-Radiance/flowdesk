import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient


def tiny_gif(name="asset.gif"):
    img_data = (
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
        b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
        b'\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
    )
    return SimpleUploadedFile(name, img_data, content_type="image/gif")


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
def test_login_accepts_non_ictu_email(django_user_model):
    django_user_model.objects.create_user(
        username="radiance84",
        email="nnamuradiance@gmail.com",
        password="password123",
        role="admin",
    )
    client = APIClient()

    response = client.post(
        reverse("auth-login"),
        {"username": "nnamuradiance@gmail.com", "password": "password123"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["user"]["email"] == "nnamuradiance@gmail.com"
    assert response.data["user"]["role"] == "admin"


@pytest.mark.django_db
def test_signup_accepts_non_ictu_email():
    client = APIClient()

    response = client.post(
        reverse("auth-signup"),
        {
            "email": "new.user@gmail.com",
            "password": "password123",
            "first_name": "New",
            "last_name": "User",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["user"]["email"] == "new.user@gmail.com"
    assert "access" in response.data


@pytest.mark.django_db
def test_magic_link_accepts_non_ictu_email(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    client = APIClient()

    response = client.post(
        reverse("auth-magic-request"),
        {"email": "magic.user@gmail.com"},
        format="json",
    )

    assert response.status_code == 202


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
    created_user = django_user_model.objects.get(email="new@example.com")
    assert created_user.approver_type == ""

    # Test Update Role
    response = client.patch(
        reverse("auth-user-role", kwargs={"pk": user.pk}),
        {"role": "approver", "approver_type": "dean"}
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.role == "approver"
    assert user.approver_type == "dean"

    response = client.patch(
        reverse("auth-user-role", kwargs={"pk": user.pk}),
        {"role": "submitter"},
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.role == "submitter"
    assert user.approver_type == ""

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

    # Keep the shared validator aligned with SimpleJWT's configured signer.
    monkeypatch.setenv("JWT_SECRET_KEY", settings.SIMPLE_JWT["SIGNING_KEY"])

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


@pytest.mark.django_db
def test_me_view_update(django_user_model):
    user = django_user_model.objects.create_user(
        username="me_user",
        password="password",
        role="submitter",
        first_name="Old",
        last_name="Name"
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(reverse("auth-me"), {"first_name": "New"}, format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "New"


@pytest.mark.django_db
def test_user_list_filters(django_user_model):
    django_user_model.objects.create_user(username="u1", role="admin", is_active=True)
    django_user_model.objects.create_user(username="u2", role="submitter", is_active=False)
    django_user_model.objects.create_user(username="u3", role="approver", approver_type="dean")
    
    admin = django_user_model.objects.filter(role="admin").first()
    client = APIClient()
    client.force_authenticate(user=admin)

    # Filter by role
    response = client.get(reverse("auth-users"), {"role": "submitter"})
    assert len(response.data) == 1
    assert response.data[0]["username"] == "u2"

    # Filter by active
    response = client.get(reverse("auth-users"), {"is_active": "false"})
    assert len(response.data) == 1
    assert response.data[0]["username"] == "u2"

    # Filter by approver_type
    response = client.get(reverse("auth-users"), {"approver_type": "dean"})
    assert len(response.data) == 1
    assert response.data[0]["username"] == "u3"


@pytest.mark.django_db
def test_user_delete(django_user_model):
    admin = django_user_model.objects.create_user(username="admin_del", role="admin")
    user = django_user_model.objects.create_user(username="to_delete", role="submitter")
    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.delete(reverse("auth-user-detail", kwargs={"pk": user.pk}))
    assert response.status_code == 204
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_submitter_can_upload_signature(django_user_model):
    user = django_user_model.objects.create_user(username="upload_user", role="submitter")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        reverse("signature-stamp-upload"),
        {"signature_image": tiny_gif("sig.gif")},
        format="multipart"
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.signature_image

    response = client.delete(reverse("signature-stamp-upload") + "?field=signature_image")
    assert response.status_code == 200
    user.refresh_from_db()
    assert not user.signature_image


@pytest.mark.django_db
def test_submitter_cannot_upload_or_delete_stamp(django_user_model):
    user = django_user_model.objects.create_user(username="submitter_stamp", role="submitter")
    user.stamp_image = "stamps/existing.gif"
    user.save(update_fields=["stamp_image"])
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        reverse("signature-stamp-upload"),
        {"stamp_image": tiny_gif("stamp.gif")},
        format="multipart",
    )

    assert response.status_code == 403
    assert response.data["detail"] == "Submitters cannot upload an official stamp."
    user.refresh_from_db()
    assert str(user.stamp_image) == "stamps/existing.gif"

    response = client.delete(reverse("signature-stamp-upload") + "?field=stamp_image")

    assert response.status_code == 403
    assert response.data["detail"] == "Submitters cannot delete an official stamp."
    user.refresh_from_db()
    assert str(user.stamp_image) == "stamps/existing.gif"


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["approver", "admin"])
def test_approver_and_admin_can_upload_stamp(django_user_model, role):
    user = django_user_model.objects.create_user(username=f"{role}_stamp", role=role)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        reverse("signature-stamp-upload"),
        {"stamp_image": tiny_gif("stamp.gif")},
        format="multipart",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.stamp_image


@pytest.mark.django_db
def test_refresh_view_errors():
    client = APIClient()
    
    # Missing refresh
    response = client.post(reverse("auth-refresh"), {}, format="json")
    assert response.status_code == 400

    # Invalid refresh
    response = client.post(reverse("auth-refresh"), {"refresh": "invalid"}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_magic_link_verify_errors():
    client = APIClient()
    
    # No token
    response = client.get(reverse("auth-magic-verify"), format="json")
    assert response.status_code == 401

    # Invalid token
    response = client.get(reverse("auth-magic-verify"), {"token": "invalid"}, format="json")
    assert response.status_code == 401
