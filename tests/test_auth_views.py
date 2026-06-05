import pytest
from django.urls import reverse
from rest_framework import status

from tests.factories import UserFactory


@pytest.mark.django_db
def test_auth_me_and_logout(api_client):
    user = UserFactory()
    api_client.force_authenticate(user=user)

    me_response = api_client.get(reverse("auth-me"))
    assert me_response.status_code == status.HTTP_200_OK
    assert me_response.data["id"] == user.id

    logout_response = api_client.post(reverse("auth-logout"))
    assert logout_response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_login_accepts_email_identifier(api_client):
    user = UserFactory(username="flowdesk_user", email="user@example.com")
    user.set_password("password123")
    user.save(update_fields=["password"])

    response = api_client.post(
        reverse("auth-login"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert response.data["user"]["email"] == "user@example.com"
