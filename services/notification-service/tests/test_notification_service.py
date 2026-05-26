import pytest
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from apps.notifications.models import Notification


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/health/")
    assert response.status_code in {200, 503}


@pytest.mark.django_db
def test_handle_event_task():
    from apps.notifications.tasks import handle_event
    
    event = {
        "event_type": "workflow.created",
        "payload": {
            "submitter_id": 42,
            "workflow_id": 1
        }
    }
    
    with patch("apps.notifications.tasks.get_channel_layer") as mock_channels, \
         patch("apps.notifications.tasks.send_email_task.delay") as mock_email:
        
        result = handle_event(event) # No .delay() to run it synchronously in test
        
        assert result["handled"] == "workflow.created"
        assert Notification.objects.filter(recipient_id=42).exists()
        mock_channels.assert_called_once()
        mock_email.assert_called_once()
