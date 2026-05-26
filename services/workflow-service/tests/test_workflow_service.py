import pytest
from rest_framework.test import APIClient

from apps.workflows.models import Workflow


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/health/")
    assert response.status_code in {200, 503}


@pytest.mark.django_db
def test_list_requires_authentication():
    Workflow.objects.create(name="Demo", created_by_id=1)
    client = APIClient()
    response = client.get("/api/workflows/")
    assert response.status_code == 401
