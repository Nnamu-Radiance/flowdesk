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
